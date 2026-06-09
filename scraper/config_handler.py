# mae_scraper/config_handler.py
import json
import os
import re

def load_config(config_filename='mae_config.json'):
    """
    Carrega as configurações do arquivo JSON especificado, ajustando o caminho 
    da pasta 'Shared drives' conforme o sistema.
    """
    try:
        # Encontra o caminho para a pasta raiz do projeto (mae_scraper/)
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Usa o nome do arquivo passado como argumento
        config_path = os.path.join(script_dir, config_filename)
        
        with open(config_path, 'r', encoding='utf-8') as f:
            print(f"Carregando configurações de '{config_path}'...")
            config = json.load(f)
            
        # A lógica para ajustar os caminhos permanece a mesma
        if os.path.exists("G:/Drives compartilhados"):
            shared_drive_root = "G:/Drives compartilhados"
        elif os.path.exists("G:/Shared drives"):
            shared_drive_root = "G:/Shared drives"
        else:
            print("Aviso: Pasta 'Shared drives' ou 'Drives compartilhados' não encontrada. Usando caminhos originais.")
            return config
            
        print(f"Ajustando caminhos para a raiz: '{shared_drive_root}'")
        for key in ["input_folder", "output_folder", "log_folder"]:
            if key in config.get("paths", {}):
                original_path = config["paths"][key]
                # Usa re.escape para tratar os nomes das pastas como texto literal
                drive_pattern = re.escape("G:/Shared drives") + '|' + re.escape("G:/Drives compartilhados")
                updated_path = re.sub(drive_pattern, shared_drive_root, original_path)
                config["paths"][key] = updated_path
                
        return config
        
    except FileNotFoundError:
        print(f"ERRO: Arquivo de configuração '{config_path}' não encontrado. Encerrando.")
        return None
    except json.JSONDecodeError:
        print(f"ERRO: Arquivo de configuração '{config_path}' não é um JSON válido. Encerrando.")
        return None