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