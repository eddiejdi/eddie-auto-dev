use reqwest;
use serde_json::{self, Value};
use clap::Parser;

#[derive(Parser)]
struct Args {
    #[clap(short, long, help = "Jira server URL")]
    jira_server: String,

    #[clap(short, long, help = "Username for Jira API")]
    username: String,

    #[clap(short, long, help = "Password for Jira API")]
    password: String,

    #[clap(short, long, help = "Issue key to track")]
    issue_key: String,
}

#[derive(Debug)]
struct JiraError {
    message: String,
}

impl std::error::Error for JiraError {}

impl std::fmt::Display for JiraError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "Jira error: {}", self.message)
    }
}

async fn get_issue_details(jira_server: &str, username: &str, password: &str, issue_key: &str) -> Result<Value, JiraError> {
    let url = format!("{}rest/api/2/issue/{}", jira_server, issue_key);
    let client = reqwest::Client::new();
    let response = client.get(url).basic_auth(username, Some(password)).send().await?;

    if !response.status().is_success() {
        return Err(JiraError {
            message: format!("Failed to fetch issue details: {}", response.text().await?),
        });
    }

    Ok(response.json::<Value>().await?)
}

async fn update_issue_status(jira_server: &str, username: &str, password: &str, issue_key: &str, status: &str) -> Result<(), JiraError> {
    let url = format!("{}rest/api/2/issue/{}/status", jira_server, issue_key);
    let client = reqwest::Client::new();
    let response = client.put(url).basic_auth(username, Some(password)).json(json!({
        "update": {
            "fields": {
                "status": {
                    "name": status
                }
            }
        }
    })).send().await?;

    if !response.status().is_success() {
        return Err(JiraError {
            message: format!("Failed to update issue status: {}", response.text().await?),
        });
    }

    Ok(())
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = Args::parse();

    let issue_details = get_issue_details(&args.jira_server, &args.username, &args.password, &args.issue_key).await?;
    println!("Issue details: {:?}", issue_details);

    let status = "In Progress";
    update_issue_status(&args.jira_server, &args.username, &args.password, &args.issue_key, status).await?;

    println!("Issue updated to {}", status);

    Ok(())
}