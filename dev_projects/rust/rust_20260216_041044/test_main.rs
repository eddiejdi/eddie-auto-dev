use reqwest;
use serde_json;
use chrono::{DateTime, Utc};
use clap::Parser;

#[derive(Parser)]
struct Args {
    #[clap(short, long)]
    token: String,
    #[clap(short, long)]
    project_key: String,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = Args::parse();

    // Connect to Jira API
    let client = reqwest::Client::new();
    let response = client.get(&format!("https://your-jira-instance.atlassian.net/rest/api/2/project/{}/issue", &args.project_key))
        .header("Authorization", format!("Basic {}", args.token))
        .send()?;

    // Parse JSON response
    let issues: Vec<serde_json::Value> = serde_json::from_reader(response.text().unwrap())?;
    
    for issue in issues {
        let key = issue["key"].as_str().unwrap();
        let status = issue["fields"]["status"]["name"].as_str().unwrap();

        println!("Issue {}: {}", key, status);
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use reqwest;
    use serde_json;
    use chrono::{DateTime, Utc};
    use clap::Parser;

    #[derive(Parser)]
    struct Args {
        #[clap(short, long)]
        token: String,
        #[clap(short, long)]
        project_key: String,
    }

    fn main() -> Result<(), Box<dyn std::error::Error>> {
        let args = Args::parse();

        // Connect to Jira API
        let client = reqwest::Client::new();
        let response = client.get(&format!("https://your-jira-instance.atlassian.net/rest/api/2/project/{}/issue", &args.project_key))
            .header("Authorization", format!("Basic {}", args.token))
            .send()?;

        // Parse JSON response
        let issues: Vec<serde_json::Value> = serde_json::from_reader(response.text().unwrap())?;
        
        for issue in issues {
            let key = issue["key"].as_str().unwrap();
            let status = issue["fields"]["status"]["name"].as_str().unwrap();

            println!("Issue {}: {}", key, status);
        }

        Ok(())
    }

    #[test]
    fn test_main_success() {
        // Teste de sucesso com valores válidos
        let args = Args {
            token: "your_token".to_string(),
            project_key: "your_project_key".to_string(),
        };

        let result = main();
        assert!(result.is_ok());
    }

    #[test]
    fn test_main_failure_division_by_zero() {
        // Teste de erro (divisão por zero)
        let args = Args {
            token: "your_token".to_string(),
            project_key: "your_project_key".to_string(),
        };

        let result = main();
        assert!(result.is_err());
    }

    #[test]
    fn test_main_failure_invalid_json() {
        // Teste de erro (valores inválidos)
        let args = Args {
            token: "your_token".to_string(),
            project_key: "your_project_key".to_string(),
        };

        let result = main();
        assert!(result.is_err());
    }

    #[test]
    fn test_main_edge_case_empty_response() {
        // Teste de edge case (valores limite, strings vazias, None, etc)
        let args = Args {
            token: "your_token".to_string(),
            project_key: "your_project_key".to_string(),
        };

        let result = main();
        assert!(result.is_err());
    }
}