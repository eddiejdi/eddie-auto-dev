"""
Agentes Especializados por Linguagem
Cada classe herda de SpecializedAgent e implementa particularidades da linguagem
"""
from typing import List, Dict, Any
from .base_agent import SpecializedAgent


class PythonAgent(SpecializedAgent):
    """Agente especializado em Python"""
    
    def __init__(self):
        super().__init__("python")
    
    @property
    def name(self) -> str:
        return "Python Expert Agent"
    
    @property
    def capabilities(self) -> List[str]:
        return [
            "FastAPI / Flask / Django APIs",
            "Data Science (pandas, numpy, scikit-learn)",
            "Automação com Selenium",
            "Scripts e CLI tools",
            "Machine Learning",
            "Web scraping",
            "Streamlit dashboards",
            "Async programming"
        ]
    
    async def generate_project_structure(self, project_name: str) -> Dict[str, str]:
        """Gera estrutura típica de projeto Python"""
        return {
            "pyproject.toml": f'''[project]
name = "{project_name}"
version = "0.1.0"
requires-python = ">=3.11"

[project.optional-dependencies]
dev = ["pytest", "black", "mypy", "ruff"]

[tool.black]
line-length = 100

[tool.ruff]
line-length = 100
select = ["E", "F", "I"]

[tool.mypy]
python_version = "3.11"
strict = true
''',
            f"{project_name}/__init__.py": f'"""Module {project_name}"""\n__version__ = "0.1.0"',
            f"{project_name}/main.py": '"""Main module"""\n\ndef main():\n    pass\n\nif __name__ == "__main__":\n    main()',
            "tests/__init__.py": "",
            "tests/test_main.py": f'"""Tests for {project_name}"""\nimport pytest\nfrom {project_name}.main import main\n\ndef test_main():\n    assert main() is None',
            "README.md": f"# {project_name}\n\n## Installation\n```bash\npip install -e .[dev]\n```\n\n## Usage\n```python\nfrom {project_name} import main\n```",
            ".gitignore": "__pycache__/\n*.pyc\n.venv/\n.mypy_cache/\n.pytest_cache/\ndist/\n*.egg-info/"
        }


class JavaScriptAgent(SpecializedAgent):
    """Agente especializado em JavaScript"""
    
    def __init__(self):
        super().__init__("javascript")
    
    @property
    def name(self) -> str:
        return "JavaScript Expert Agent"
    
    @property
    def capabilities(self) -> List[str]:
        return [
            "Node.js servers (Express, Fastify)",
            "React applications",
            "Vue.js applications",
            "REST APIs",
            "GraphQL APIs",
            "Real-time (Socket.io)",
            "CLI tools",
            "Testing with Jest"
        ]
    
    async def generate_project_structure(self, project_name: str) -> Dict[str, str]:
        """Gera estrutura típica de projeto Node.js"""
        return {
            "package.json": f'''{{
  "name": "{project_name}",
  "version": "1.0.0",
  "main": "src/index.js",
  "scripts": {{
    "start": "node src/index.js",
    "dev": "nodemon src/index.js",
    "test": "jest",
    "lint": "eslint src/"
  }},
  "devDependencies": {{
    "jest": "^29.0.0",
    "eslint": "^8.0.0",
    "nodemon": "^3.0.0"
  }}
}}''',
            "src/index.js": f'// {project_name} entry point\nconsole.log("Starting {project_name}...");\n',
            "src/app.js": 'module.exports = { hello: () => "Hello World" };',
            "tests/app.test.js": 'const app = require("../src/app");\n\ntest("hello returns greeting", () => {\n  expect(app.hello()).toBe("Hello World");\n});',
            ".eslintrc.json": '{\n  "env": { "node": true, "jest": true },\n  "extends": "eslint:recommended"\n}',
            "README.md": f"# {project_name}\n\n## Install\n```bash\nnpm install\n```\n\n## Run\n```bash\nnpm start\n```",
            ".gitignore": "node_modules/\n.env\ncoverage/"
        }


class TypeScriptAgent(SpecializedAgent):
    """Agente especializado em TypeScript"""
    
    def __init__(self):
        super().__init__("typescript")
    
    @property
    def name(self) -> str:
        return "TypeScript Expert Agent"
    
    @property
    def capabilities(self) -> List[str]:
        return [
            "Type-safe Node.js servers",
            "React with TypeScript",
            "Next.js applications",
            "NestJS backends",
            "GraphQL with type generation",
            "Strongly-typed APIs",
            "Complex type systems",
            "Monorepo setups"
        ]
    
    async def generate_project_structure(self, project_name: str) -> Dict[str, str]:
        """Gera estrutura típica de projeto TypeScript"""
        return {
            "package.json": f'''{{
  "name": "{project_name}",
  "version": "1.0.0",
  "main": "dist/index.js",
  "scripts": {{
    "build": "tsc",
    "start": "node dist/index.js",
    "dev": "ts-node src/index.ts",
    "test": "jest",
    "lint": "eslint src/"
  }},
  "devDependencies": {{
    "typescript": "^5.0.0",
    "@types/node": "^20.0.0",
    "ts-node": "^10.0.0",
    "jest": "^29.0.0",
    "@types/jest": "^29.0.0",
    "ts-jest": "^29.0.0"
  }}
}}''',
            "tsconfig.json": '''{
  "compilerOptions": {
    "target": "ES2022",
    "module": "commonjs",
    "lib": ["ES2022"],
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "declaration": true
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist"]
}''',
            "src/index.ts": f'// {project_name} entry point\nconsole.log("Starting {project_name}...");\n\nexport function main(): void {{\n  console.log("Hello from TypeScript!");\n}}\n\nmain();',
            "src/types.ts": '// Type definitions\nexport interface Config {\n  name: string;\n  debug: boolean;\n}',
            "tests/index.test.ts": 'import { main } from "../src/index";\n\ndescribe("main", () => {\n  it("should run without errors", () => {\n    expect(() => main()).not.toThrow();\n  });\n});',
            "jest.config.js": 'module.exports = {\n  preset: "ts-jest",\n  testEnvironment: "node"\n};',
            "README.md": f"# {project_name}\n\n## Build\n```bash\nnpm run build\n```\n\n## Dev\n```bash\nnpm run dev\n```",
            ".gitignore": "node_modules/\ndist/\n.env\ncoverage/"
        }


class GoAgent(SpecializedAgent):
    """Agente especializado em Go"""
    
    def __init__(self):
        super().__init__("go")
    
    @property
    def name(self) -> str:
        return "Go Expert Agent"
    
    @property
    def capabilities(self) -> List[str]:
        return [
            "High-performance HTTP servers",
            "Microservices",
            "CLI applications",
            "Concurrent programming",
            "gRPC services",
            "Database operations",
            "Cloud-native apps",
            "DevOps tooling"
        ]
    
    async def generate_project_structure(self, project_name: str) -> Dict[str, str]:
        """Gera estrutura típica de projeto Go"""
        return {
            "go.mod": f'module {project_name}\n\ngo 1.22\n',
            "main.go": f'''package main

import "fmt"

func main() {{
    fmt.Println("Hello from {project_name}!")
}}

func Add(a, b int) int {{
    return a + b
}}
''',
            "main_test.go": '''package main

import "testing"

func TestAdd(t *testing.T) {
    result := Add(2, 3)
    if result != 5 {
        t.Errorf("Add(2, 3) = %d; want 5", result)
    }
}
''',
            "Makefile": f'''PROJECT = {project_name}

build:
\tgo build -o bin/$(PROJECT) .

test:
\tgo test -v ./...

run:
\tgo run .

clean:
\trm -rf bin/
''',
            "README.md": f"# {project_name}\n\n## Build\n```bash\nmake build\n```\n\n## Test\n```bash\nmake test\n```",
            ".gitignore": "bin/\n*.exe\n.env"
        }


class RustAgent(SpecializedAgent):
    """Agente especializado em Rust"""
    
    def __init__(self):
        super().__init__("rust")
    
    @property
    def name(self) -> str:
        return "Rust Expert Agent"
    
    @property
    def capabilities(self) -> List[str]:
        return [
            "Systems programming",
            "High-performance servers",
            "WebAssembly",
            "CLI applications (clap)",
            "Async with Tokio",
            "Memory-safe code",
            "Embedded systems",
            "Cryptography"
        ]
    
    async def generate_project_structure(self, project_name: str) -> Dict[str, str]:
        """Gera estrutura típica de projeto Rust"""
        return {
            "Cargo.toml": f'''[package]
name = "{project_name}"
version = "0.1.0"
edition = "2021"

[dependencies]
tokio = {{ version = "1", features = ["full"] }}
serde = {{ version = "1", features = ["derive"] }}
serde_json = "1"

[dev-dependencies]
''',
            "src/main.rs": f'''//! {project_name} - Main entry point

fn main() {{
    println!("Hello from {project_name}!");
}}

pub fn add(a: i32, b: i32) -> i32 {{
    a + b
}}

#[cfg(test)]
mod tests {{
    use super::*;

    #[test]
    fn test_add() {{
        assert_eq!(add(2, 3), 5);
    }}
}}
''',
            "src/lib.rs": f'//! {project_name} library\n\npub mod utils;\n',
            "src/utils.rs": '//! Utility functions\n\npub fn greet(name: &str) -> String {\n    format!("Hello, {}!", name)\n}',
            "README.md": f"# {project_name}\n\n## Build\n```bash\ncargo build --release\n```\n\n## Test\n```bash\ncargo test\n```",
            ".gitignore": "target/\nCargo.lock\n.env"
        }


class JavaAgent(SpecializedAgent):
    """Agente especializado em Java"""
    
    def __init__(self):
        super().__init__("java")
    
    @property
    def name(self) -> str:
        return "Java Expert Agent"
    
    @property
    def capabilities(self) -> List[str]:
        return [
            "Spring Boot applications",
            "REST APIs",
            "Microservices",
            "Enterprise applications",
            "Android development",
            "JPA/Hibernate",
            "Maven/Gradle builds",
            "Testing with JUnit"
        ]
    
    async def generate_project_structure(self, project_name: str) -> Dict[str, str]:
        """Gera estrutura típica de projeto Java/Maven"""
        package_path = project_name.replace("-", "").lower()
        return {
            "pom.xml": f'''<?xml version="1.0" encoding="UTF-8"?>
<project>
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.example</groupId>
    <artifactId>{project_name}</artifactId>
    <version>1.0.0</version>
    <packaging>jar</packaging>
    
    <properties>
        <maven.compiler.source>21</maven.compiler.source>
        <maven.compiler.target>21</maven.compiler.target>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    </properties>
    
    <dependencies>
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter</artifactId>
            <version>5.10.0</version>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>
''',
            f"src/main/java/com/example/{package_path}/Main.java": f'''package com.example.{package_path};

public class Main {{
    public static void main(String[] args) {{
        System.out.println("Hello from {project_name}!");
    }}
    
    public static int add(int a, int b) {{
        return a + b;
    }}
}}
''',
            f"src/test/java/com/example/{package_path}/MainTest.java": f'''package com.example.{package_path};

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class MainTest {{
    @Test
    void testAdd() {{
        assertEquals(5, Main.add(2, 3));
    }}
}}
''',
            "README.md": f"# {project_name}\n\n## Build\n```bash\nmvn package\n```\n\n## Test\n```bash\nmvn test\n```",
            ".gitignore": "target/\n*.class\n*.jar\n.idea/\n*.iml"
        }


class CSharpAgent(SpecializedAgent):
    """Agente especializado em C#"""
    
    def __init__(self):
        super().__init__("csharp")
    
    @property
    def name(self) -> str:
        return "C# Expert Agent"
    
    @property
    def capabilities(self) -> List[str]:
        return [
            "ASP.NET Core Web APIs",
            ".NET MAUI/Blazor",
            "Entity Framework Core",
            "Microservices",
            "Azure integrations",
            "Desktop applications (WPF/WinForms)",
            "Game development (Unity)",
            "Testing with xUnit"
        ]
    
    async def generate_project_structure(self, project_name: str) -> Dict[str, str]:
        """Gera estrutura típica de projeto C#"""
        namespace = project_name.replace("-", "").replace("_", "")
        return {
            f"{project_name}.csproj": f'''<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net8.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="xunit" Version="2.6.0" />
    <PackageReference Include="xunit.runner.visualstudio" Version="2.5.0" />
  </ItemGroup>
</Project>
''',
            "Program.cs": f'''namespace {namespace};

class Program
{{
    static void Main(string[] args)
    {{
        Console.WriteLine("Hello from {project_name}!");
    }}
    
    public static int Add(int a, int b) => a + b;
}}
''',
            "Tests/ProgramTests.cs": f'''namespace {namespace}.Tests;

using Xunit;

public class ProgramTests
{{
    [Fact]
    public void Add_ShouldReturnSum()
    {{
        Assert.Equal(5, Program.Add(2, 3));
    }}
}}
''',
            "README.md": f"# {project_name}\n\n## Build\n```bash\ndotnet build\n```\n\n## Test\n```bash\ndotnet test\n```",
            ".gitignore": "bin/\nobj/\n*.user\n.vs/"
        }


class PHPAgent(SpecializedAgent):
    """Agente especializado em PHP"""
    
    def __init__(self):
        super().__init__("php")
    
    @property
    def name(self) -> str:
        return "PHP Expert Agent"
    
    @property
    def capabilities(self) -> List[str]:
        return [
            "Laravel applications",
            "Symfony projects",
            "REST APIs",
            "WordPress development",
            "E-commerce (Magento, WooCommerce)",
            "Composer packages",
            "Testing with PHPUnit",
            "Modern PHP 8.x"
        ]
    
    async def generate_project_structure(self, project_name: str) -> Dict[str, str]:
        """Gera estrutura típica de projeto PHP"""
        namespace = ''.join(word.capitalize() for word in project_name.replace("-", "_").split("_"))
        return {
            "composer.json": f'''{{
    "name": "example/{project_name}",
    "description": "{project_name} project",
    "type": "project",
    "require": {{
        "php": ">=8.2"
    }},
    "require-dev": {{
        "phpunit/phpunit": "^10.0"
    }},
    "autoload": {{
        "psr-4": {{
            "{namespace}\\\\": "src/"
        }}
    }},
    "autoload-dev": {{
        "psr-4": {{
            "{namespace}\\\\Tests\\\\": "tests/"
        }}
    }}
}}
''',
            "src/Main.php": f'''<?php

declare(strict_types=1);

namespace {namespace};

class Main
{{
    public function greet(string $name = "World"): string
    {{
        return "Hello, $name!";
    }}
    
    public function add(int $a, int $b): int
    {{
        return $a + $b;
    }}
}}
''',
            "tests/MainTest.php": f'''<?php

declare(strict_types=1);

namespace {namespace}\\Tests;

use PHPUnit\\Framework\\TestCase;
use {namespace}\\Main;

class MainTest extends TestCase
{{
    public function testAdd(): void
    {{
        $main = new Main();
        $this->assertEquals(5, $main->add(2, 3));
    }}
    
    public function testGreet(): void
    {{
        $main = new Main();
        $this->assertEquals("Hello, PHP!", $main->greet("PHP"));
    }}
}}
''',
            "phpunit.xml": '''<?xml version="1.0" encoding="UTF-8"?>
<phpunit bootstrap="vendor/autoload.php" colors="true">
    <testsuites>
        <testsuite name="Tests">
            <directory>tests</directory>
        </testsuite>
    </testsuites>
</phpunit>
''',
            "README.md": f"# {project_name}\n\n## Install\n```bash\ncomposer install\n```\n\n## Test\n```bash\nvendor/bin/phpunit\n```",
            ".gitignore": "vendor/\n.env\n*.cache"
        }


# Factory para criar agentes
AGENT_CLASSES = {
    "python": PythonAgent,
    "javascript": JavaScriptAgent,
    "typescript": TypeScriptAgent,
    "go": GoAgent,
    "rust": RustAgent,
    "java": JavaAgent,
    "csharp": CSharpAgent,
    "php": PHPAgent,
    # Agentes especializados (não são linguagens)
    # "bpm": BPMAgent - carregado via specialized_agents.bpm_agent
}

def create_agent(language: str) -> SpecializedAgent:
    """Factory para criar agente baseado na linguagem"""
    agent_class = AGENT_CLASSES.get(language.lower())
    if not agent_class:
        raise ValueError(f"Linguagem não suportada: {language}")
    # Retornar uma instância que inclua o JiraAgentMixin para garantir
    # que métodos Jira (jira_start_ticket, jira_submit_for_review, etc.)
    # estejam disponíveis nas instâncias criadas.
    try:
        # Import local para evitar dependência circular em tempo de import
        from specialized_agents.jira.agent_mixin import JiraAgentMixin

        Combined = type(f"{agent_class.__name__}WithJira", (JiraAgentMixin, agent_class), {})
        return Combined()
    except Exception:
        # Fallback: instanciar agente sem mixin se houver qualquer erro
        return agent_class()


# Função para obter agentes especializados (não-linguagens)
def get_specialized_agent(agent_type: str):
    """Retorna agente especializado por tipo"""
    if agent_type.lower() == "bpm":
        from .bpm_agent import get_bpm_agent
        return get_bpm_agent()
    if agent_type.lower() in ("home", "home_automation", "google_assistant", "smart_home"):
        from .home_automation import get_google_assistant_agent
        return get_google_assistant_agent()
    raise ValueError(f"Agente especializado não encontrado: {agent_type}")
