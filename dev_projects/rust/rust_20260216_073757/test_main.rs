use reqwest;
use serde_json::{self, Value};
use clap::Parser;

#[derive(Parser)]
struct Cli {
    #[clap(short, long, default_value = "http://localhost:8080")]
    server_url: String,

    #[clap(short, long, default_value = "123456789")]
    project_key: String,

    #[clap(short, long)]
    issue_id: Option<String>,

    #[clap(short, long)]
    summary: Option<String>,
}

async fn send_request(url: &str, method: &str, body: &Value) -> Result<Value, reqwest::Error> {
    let client = reqwest::Client::new();
    let response = match method {
        "POST" => client.post(url).json(body).send(),
        "PUT" => client.put(url).json(body).send(),
        _ => client.get(url).send(),
    }?;

    response.json()
}

async fn create_issue(server_url: &str, project_key: &str, issue_id: Option<&str>, summary: Option<&str>) -> Result<Value, reqwest::Error> {
    let body = serde_json!({
        "fields": {
            "project": {
                "key": project_key
            },
            "summary": summary,
            "description": "Created by Rust Agent",
            "issuetype": {
                "name": "Bug"
            }
        }
    });

    send_request(&format!("{}rest/api/2/issue", server_url), "POST", &body)
}

async fn update_issue(server_url: &str, issue_id: &str, summary: Option<&str>) -> Result<Value, reqwest::Error> {
    let body = serde_json!({
        "fields": {
            "summary": summary
        }
    });

    send_request(&format!("{}rest/api/2/issue/{}/update", server_url, issue_id), "PUT", &body)
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let cli = Cli::parse();

    if cli.issue_id.is_none() && cli.summary.is_none() {
        println!("Please provide either issue ID or summary.");
        return Ok(());
    }

    match cli.issue_id {
        Some(issue_id) => {
            let response = create_issue(&cli.server_url, &cli.project_key, Some(issue_id), None).await?;
            assert_eq!(response["id"], "123456789");
            println!("Issue created: {:?}", response);
        }
        None => {
            let response = update_issue(&cli.server_url, &cli.project_key, cli.summary.as_deref()).await?;
            assert_eq!(response["summary"], "Updated summary");
            println!("Issue updated: {:?}", response);
        }
    }

    Ok(())
}