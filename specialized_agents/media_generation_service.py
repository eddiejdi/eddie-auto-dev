"""
Media Generation Service — Geração de imagens e vídeos via diffusers.

Orquestração:
- GPU1 (GTX 1050, qwen3:0.6b) atua como controller — recebe requisições,
  refina prompts e coordena a geração.
- GPU0 (RTX 2060 SUPER, 8GB) executa os pipelines diffusers.
- VRAMSwapManager garante exclusão mútua entre Ollama LLM e diffusers na GPU0.

Pipelines sob demanda:
- Imagem: SD 1.5, SDXL Turbo, SD3 Medium
- Vídeo: CogVideoX-2B, LTX-Video, Wan2.1-T2V-1.3B, AnimateDiff

Modelos baixados para /mnt/raid1/models/ na primeira utilização.
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from .config import (
    DATA_DIR,
    LLM_GPU1_CONFIG,
    MEDIA_GENERATION_CONFIG,
)
from .vram_swap_manager import VRAMSwapManager

logger = logging.getLogger(__name__)


class MediaType(Enum):
    """Tipo de mídia a gerar."""
    IMAGE = "image"
    VIDEO = "video"


class GenerationStatus(Enum):
    """Status de uma requisição de geração."""
    QUEUED = "queued"
    REFINING_PROMPT = "refining_prompt"
    SWAPPING_VRAM = "swapping_vram"
    LOADING_PIPELINE = "loading_pipeline"
    GENERATING = "generating"
    SAVING = "saving"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class MediaRequest:
    """Requisição de geração de mídia."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    prompt: str = ""
    pipeline_id: str = "sd15"
    media_type: str = "image"
    num_inference_steps: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    guidance_scale: float = 7.5
    num_images: int = 1
    num_frames: Optional[int] = None
    fps: Optional[int] = None
    refine_prompt: bool = True
    source_agent: str = "user"
    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )


@dataclass
class MediaResult:
    """Resultado da geração de mídia."""
    request_id: str
    status: str
    media_type: str = "image"
    output_paths: List[str] = field(default_factory=list)
    refined_prompt: Optional[str] = None
    pipeline_used: str = ""
    generation_time_s: float = 0.0
    swap_time_s: float = 0.0
    vram_peak_mb: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return asdict(self)


class MediaGenerationService:
    """
    Serviço de geração de imagens e vídeos coordenado por GPU1.

    GPU1 (qwen3:0.6b) refina prompts e supervisiona.
    GPU0 (RTX 2060) executa os pipelines diffusers.
    VRAMSwapManager garante exclusão mútua na GPU0.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Inicializa o serviço de geração de mídia.

        Args:
            config: Configuração customizada (usa MEDIA_GENERATION_CONFIG se None).
        """
        self._config = config or MEDIA_GENERATION_CONFIG
        self._gpu1_url = LLM_GPU1_CONFIG["base_url"]
        self._gpu1_model = LLM_GPU1_CONFIG["model"]

        # Diretórios
        self._models_dir = Path(self._config["models_dir"])
        self._output_dir = Path(self._config.get("output_dir", DATA_DIR / "media_output"))
        self._output_dir.mkdir(parents=True, exist_ok=True)

        # VRAM Swap Manager
        self._swap_manager = VRAMSwapManager(
            unload_timeout=self._config.get("swap_unload_timeout_s", 30),
            reload_timeout=self._config.get("swap_reload_timeout_s", 120),
        )

        # Pipeline cache (mantém último pipeline carregado em memória)
        self._loaded_pipeline: Optional[Any] = None
        self._loaded_pipeline_id: Optional[str] = None

        # Fila de requisições
        self._queue: asyncio.Queue[MediaRequest] = asyncio.Queue()
        self._processing = False

        logger.info(
            f"MediaGenerationService inicializado — "
            f"models_dir={self._models_dir}, "
            f"output_dir={self._output_dir}"
        )

    @property
    def available_pipelines(self) -> Dict[str, Dict]:
        """Retorna pipelines configurados."""
        return self._config.get("pipelines", {})

    def is_pipeline_downloaded(self, pipeline_id: str) -> bool:
        """
        Verifica se o pipeline está baixado localmente.

        Args:
            pipeline_id: ID do pipeline (ex: 'sd15', 'cogvideo_2b').
        """
        pipeline_cfg = self.available_pipelines.get(pipeline_id)
        if not pipeline_cfg:
            return False
        model_path = self._models_dir / pipeline_cfg["model_id"].replace("/", "--")
        return model_path.exists()

    def get_pipeline_status(self) -> Dict[str, Any]:
        """Retorna status de todos os pipelines."""
        result = {}
        for pid, pcfg in self.available_pipelines.items():
            result[pid] = {
                "name": pcfg["name"],
                "type": pcfg["type"],
                "vram_gb": pcfg["vram_gb"],
                "downloaded": self.is_pipeline_downloaded(pid),
                "loaded": self._loaded_pipeline_id == pid,
            }
        return result

    async def _refine_prompt_via_gpu1(self, prompt: str, media_type: str) -> str:
        """
        Usa GPU1 (qwen3:0.6b) para refinar o prompt de geração.

        Args:
            prompt: Prompt original do usuário.
            media_type: 'image' ou 'video'.

        Returns:
            Prompt refinado para o pipeline diffusers.
        """
        system_prompt = (
            f"Refine this {media_type} generation prompt for a diffusion model. "
            "Add visual details, style, lighting, quality keywords. "
            "Reply ONLY with the refined prompt in English, no explanations."
        )

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self._gpu1_url}/api/generate",
                    json={
                        "model": self._gpu1_model,
                        "prompt": f"{system_prompt}\n\nOriginal: {prompt}",
                        "stream": False,
                        "temperature": 0.7,
                    },
                )
                resp.raise_for_status()
                refined = resp.json().get("response", "").strip()
                if refined:
                    logger.info(f"Prompt refinado: {refined[:100]}...")
                    return refined
        except Exception as e:
            logger.warning(f"Falha ao refinar prompt via GPU1: {e}")

        return prompt

    def _load_image_pipeline(self, pipeline_id: str) -> Any:
        """
        Carrega pipeline de geração de imagem.

        Args:
            pipeline_id: ID do pipeline configurado.

        Returns:
            Pipeline diffusers pronto para uso.
        """
        import torch
        from diffusers.pipelines.stable_diffusion.pipeline_stable_diffusion import (
            StableDiffusionPipeline,
        )
        from diffusers.pipelines.auto_pipeline import AutoPipelineForText2Image

        pcfg = self.available_pipelines[pipeline_id]
        model_id = pcfg["model_id"]
        cache_dir = str(self._models_dir)
        device = self._config.get("device", "cuda:0")

        logger.info(f"Carregando pipeline de imagem: {pcfg['name']} ({model_id})")

        if pipeline_id == "sd15":
            pipeline = StableDiffusionPipeline.from_pretrained(
                model_id,
                torch_dtype=torch.float16,
                cache_dir=cache_dir,
            )
        else:
            pipeline = AutoPipelineForText2Image.from_pretrained(
                model_id,
                torch_dtype=torch.float16,
                cache_dir=cache_dir,
            )

        pipeline = pipeline.to(device)
        pipeline.set_progress_bar_config(disable=True)

        logger.info(f"Pipeline {pcfg['name']} carregado em {device}")
        return pipeline

    def _load_video_pipeline(self, pipeline_id: str) -> Any:
        """
        Carrega pipeline de geração de vídeo.

        Args:
            pipeline_id: ID do pipeline configurado.

        Returns:
            Pipeline diffusers pronto para uso.
        """
        import torch

        pcfg = self.available_pipelines[pipeline_id]
        model_id = pcfg["model_id"]
        cache_dir = str(self._models_dir)
        device = self._config.get("device", "cuda:0")

        logger.info(f"Carregando pipeline de vídeo: {pcfg['name']} ({model_id})")

        if pipeline_id == "cogvideo_2b":
            from diffusers.pipelines.cogvideo.pipeline_cogvideox import CogVideoXPipeline
            pipeline = CogVideoXPipeline.from_pretrained(
                model_id,
                torch_dtype=torch.float16,
                cache_dir=cache_dir,
            )
        elif pipeline_id == "ltx_video":
            from diffusers.pipelines.ltx.pipeline_ltx import LTXPipeline
            pipeline = LTXPipeline.from_pretrained(
                model_id,
                torch_dtype=torch.float16,
                cache_dir=cache_dir,
            )
        elif pipeline_id == "wan_video":
            from diffusers.pipelines.wan.pipeline_wan import WanPipeline
            pipeline = WanPipeline.from_pretrained(
                model_id,
                torch_dtype=torch.float16,
                cache_dir=cache_dir,
            )
        elif pipeline_id == "animatediff":
            from diffusers.pipelines.animatediff.pipeline_animatediff import (
                AnimateDiffPipeline,
            )
            from diffusers.models.unets.unet_motion_model import MotionAdapter
            from diffusers.pipelines.stable_diffusion.pipeline_stable_diffusion import (
                StableDiffusionPipeline as SD15Pipeline,
            )
            base_model = pcfg.get("base_model", "sd-legacy/stable-diffusion-v1-5")
            adapter = MotionAdapter.from_pretrained(
                model_id,
                torch_dtype=torch.float16,
                cache_dir=cache_dir,
            )
            pipeline = AnimateDiffPipeline.from_pretrained(
                base_model,
                motion_adapter=adapter,
                torch_dtype=torch.float16,
                cache_dir=cache_dir,
            )
        else:
            raise ValueError(f"Pipeline de vídeo desconhecido: {pipeline_id}")

        pipeline = pipeline.to(device)
        pipeline.set_progress_bar_config(disable=True)

        logger.info(f"Pipeline {pcfg['name']} carregado em {device}")
        return pipeline

    def _unload_pipeline(self) -> None:
        """Descarrega pipeline atual e libera VRAM."""
        if self._loaded_pipeline is not None:
            logger.info(f"Descarregando pipeline: {self._loaded_pipeline_id}")
            del self._loaded_pipeline
            self._loaded_pipeline = None
            self._loaded_pipeline_id = None

            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass

    async def generate(self, request: MediaRequest) -> MediaResult:
        """
        Gera mídia (imagem ou vídeo) a partir de uma requisição.

        Fluxo completo:
        1. Refina prompt via GPU1 (controller)
        2. Adquire GPU0 (swap VRAM — descarrega Ollama LLM)
        3. Carrega pipeline diffusers
        4. Gera mídia
        5. Salva resultado
        6. Libera GPU0 (recarrega Ollama LLM)

        Args:
            request: Requisição de geração.

        Returns:
            Resultado com caminhos dos arquivos gerados.
        """
        result = MediaResult(
            request_id=request.id,
            status=GenerationStatus.QUEUED.value,
            media_type=request.media_type,
            pipeline_used=request.pipeline_id,
        )

        pipeline_cfg = self.available_pipelines.get(request.pipeline_id)
        if not pipeline_cfg:
            result.status = GenerationStatus.FAILED.value
            result.error = f"Pipeline desconhecido: {request.pipeline_id}"
            return result

        total_start = time.monotonic()

        try:
            # 1. Refinar prompt via GPU1
            prompt = request.prompt
            if request.refine_prompt:
                result.status = GenerationStatus.REFINING_PROMPT.value
                prompt = await self._refine_prompt_via_gpu1(
                    prompt, request.media_type
                )
                result.refined_prompt = prompt

            # 2-6. Dentro do context manager de swap
            async with self._swap_manager.gpu0_for_media():
                swap_start = time.monotonic()
                result.status = GenerationStatus.LOADING_PIPELINE.value

                # Carregar pipeline (se diferente do atual ou novo)
                if self._loaded_pipeline_id != request.pipeline_id:
                    self._unload_pipeline()
                    if pipeline_cfg["type"] == "image":
                        self._loaded_pipeline = self._load_image_pipeline(
                            request.pipeline_id
                        )
                    else:
                        self._loaded_pipeline = self._load_video_pipeline(
                            request.pipeline_id
                        )
                    self._loaded_pipeline_id = request.pipeline_id

                result.swap_time_s = time.monotonic() - swap_start

                # Gerar mídia
                result.status = GenerationStatus.GENERATING.value
                gen_start = time.monotonic()

                if pipeline_cfg["type"] == "image":
                    output_paths = await self._generate_image(
                        request, pipeline_cfg, prompt
                    )
                else:
                    output_paths = await self._generate_video(
                        request, pipeline_cfg, prompt
                    )

                result.generation_time_s = time.monotonic() - gen_start
                result.output_paths = output_paths
                result.status = GenerationStatus.COMPLETED.value

                # Medir VRAM peak
                try:
                    import torch
                    if torch.cuda.is_available():
                        result.vram_peak_mb = (
                            torch.cuda.max_memory_allocated(0) / (1024 ** 2)
                        )
                except ImportError:
                    pass

                # Descarregar pipeline antes de devolver GPU0 ao Ollama
                self._unload_pipeline()

        except Exception as e:
            result.status = GenerationStatus.FAILED.value
            result.error = str(e)
            logger.error(f"Erro na geração de mídia: {e}", exc_info=True)

        total_time = time.monotonic() - total_start
        logger.info(
            f"Geração {result.status}: {request.pipeline_id} "
            f"em {total_time:.1f}s (swap={result.swap_time_s:.1f}s, "
            f"gen={result.generation_time_s:.1f}s)"
        )

        return result

    async def _generate_image(
        self,
        request: MediaRequest,
        pipeline_cfg: Dict,
        prompt: str,
    ) -> List[str]:
        """
        Gera imagem(ns) com pipeline diffusers carregado.

        Args:
            request: Requisição original.
            pipeline_cfg: Configuração do pipeline.
            prompt: Prompt (possivelmente refinado).

        Returns:
            Lista de caminhos dos arquivos gerados.
        """
        import torch

        width = request.width or pipeline_cfg["default_size"][0]
        height = request.height or pipeline_cfg["default_size"][1]
        steps = request.num_inference_steps or pipeline_cfg["default_steps"]

        logger.info(
            f"Gerando imagem: {width}x{height}, {steps} steps, "
            f"guidance={request.guidance_scale}"
        )

        # Executa em thread separada para não bloquear asyncio
        loop = asyncio.get_event_loop()
        assert self._loaded_pipeline is not None, "Pipeline não carregado"
        pipeline = self._loaded_pipeline
        images = await loop.run_in_executor(
            None,
            lambda: pipeline(
                prompt=prompt,
                negative_prompt="blurry, low quality, distorted, deformed",
                num_inference_steps=steps,
                guidance_scale=request.guidance_scale,
                height=height,
                width=width,
                num_images_per_prompt=request.num_images,
                generator=torch.Generator("cuda").manual_seed(42),
            ).images,
        )

        # Salvar
        output_paths = []
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        for idx, img in enumerate(images):
            filename = f"{request.pipeline_id}_{ts}_{request.id[:8]}_{idx}.png"
            filepath = self._output_dir / filename
            img.save(filepath)
            output_paths.append(str(filepath))
            logger.info(f"Imagem salva: {filepath}")

        return output_paths

    async def _generate_video(
        self,
        request: MediaRequest,
        pipeline_cfg: Dict,
        prompt: str,
    ) -> List[str]:
        """
        Gera vídeo com pipeline diffusers carregado.

        Args:
            request: Requisição original.
            pipeline_cfg: Configuração do pipeline.
            prompt: Prompt (possivelmente refinado).

        Returns:
            Lista de caminhos dos arquivos gerados.
        """
        import torch

        width = request.width or pipeline_cfg["default_size"][1]
        height = request.height or pipeline_cfg["default_size"][0]
        steps = request.num_inference_steps or pipeline_cfg["default_steps"]
        num_frames = request.num_frames or pipeline_cfg.get("default_frames", 16)
        fps = request.fps or pipeline_cfg.get("default_fps", 8)

        logger.info(
            f"Gerando vídeo: {width}x{height}, {steps} steps, "
            f"{num_frames} frames @ {fps} fps"
        )

        # Executar em thread para não bloquear
        loop = asyncio.get_event_loop()
        assert self._loaded_pipeline is not None, "Pipeline não carregado"
        pipeline = self._loaded_pipeline

        gen_kwargs: Dict[str, Any] = {
            "prompt": prompt,
            "num_inference_steps": steps,
            "guidance_scale": request.guidance_scale,
            "height": height,
            "width": width,
            "num_frames": num_frames,
            "generator": torch.Generator("cuda").manual_seed(42),
        }

        frames = await loop.run_in_executor(
            None,
            lambda: pipeline(**gen_kwargs).frames,
        )

        # Salvar como MP4
        output_paths = []
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{request.pipeline_id}_{ts}_{request.id[:8]}.mp4"
        filepath = self._output_dir / filename

        try:
            from diffusers.utils import export_to_video  # type: ignore[attr-defined]
            export_to_video(frames[0] if isinstance(frames, list) else frames, str(filepath), fps=fps)
        except ImportError:
            # Fallback: salvar frames individuais como PNGs
            frames_dir = self._output_dir / f"{request.id[:8]}_frames"
            frames_dir.mkdir(exist_ok=True)
            frame_list = frames[0] if isinstance(frames, list) else frames
            for i, frame in enumerate(frame_list):
                frame_path = frames_dir / f"frame_{i:04d}.png"
                if hasattr(frame, "save"):
                    frame.save(frame_path)
            filepath = frames_dir
            logger.warning(
                "diffusers.utils.export_to_video não disponível — "
                "frames salvos como PNGs"
            )

        output_paths.append(str(filepath))
        logger.info(f"Vídeo salvo: {filepath}")

        return output_paths

    async def download_pipeline(self, pipeline_id: str) -> bool:
        """
        Baixa modelo de pipeline para disco local (não carrega na GPU).

        Útil para pré-baixar modelos sem impactar a VRAM.

        Args:
            pipeline_id: ID do pipeline a baixar.

        Returns:
            True se baixou com sucesso.
        """
        pipeline_cfg = self.available_pipelines.get(pipeline_id)
        if not pipeline_cfg:
            logger.error(f"Pipeline desconhecido: {pipeline_id}")
            return False

        model_id = pipeline_cfg["model_id"]
        cache_dir = str(self._models_dir)

        logger.info(f"Baixando modelo: {pipeline_cfg['name']} ({model_id})...")

        try:
            from huggingface_hub import snapshot_download
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: snapshot_download(
                    model_id,
                    cache_dir=cache_dir,
                    local_dir_use_symlinks=True,
                ),
            )
            logger.info(f"Modelo {pipeline_cfg['name']} baixado com sucesso")
            return True
        except Exception as e:
            logger.error(f"Erro ao baixar modelo {model_id}: {e}")
            return False

    async def health_check(self) -> Dict[str, Any]:
        """
        Verifica saúde do serviço de geração de mídia.

        Returns:
            Dict com status do serviço, pipelines e GPUs.
        """
        swap_health = await self._swap_manager.health_check()

        return {
            "service": "media_generation",
            "enabled": self._config.get("enabled", True),
            "gpu0_swap": swap_health,
            "loaded_pipeline": self._loaded_pipeline_id,
            "queue_size": self._queue.qsize(),
            "processing": self._processing,
            "pipelines": self.get_pipeline_status(),
            "models_dir": str(self._models_dir),
            "output_dir": str(self._output_dir),
        }
