import os

def listar_arquivos(diretorio):
    try:
        arquivos = os.listdir(diretorio)
        return arquivos
    except FileNotFoundError:
        print(f"O diretório '{diretorio}' não foi encontrado.")
        return []
    except Exception as e:
        print(f"Um erro ocorreu: {e}")
        return []

def main():
    diretorio = input("Digite o caminho do diretório: ")
    
    if not os.path.exists(diretorio):
        print("O diretório não existe. Tente novamente.")
        return
    
    arquivos = listar_arquivos(diretorio)
    
    if arquivos:
        print(f"Arquivos no diretório '{diretorio}':")
        for arquivo in arquivos:
            print(arquivo)
    else:
        print("O diretório está vazio.")

if __name__ == "__main__":
    main()