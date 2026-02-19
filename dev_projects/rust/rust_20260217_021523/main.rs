use std::fs;
use std::io::{self, BufRead};
use clap::Parser;

#[derive(Parser)]
struct Args {
    file: String,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = Args::parse();

    // Leitura do arquivo
    let contents = fs::read_to_string(&args.file)?;
    
    // Processamento dos dados (por exemplo, separação por linhas)
    let lines: Vec<&str> = contents.lines().collect();
    
    // Exibição das linhas processadas
    for line in lines {
        println!("{}", line);
    }

    Ok(())
}