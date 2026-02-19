use reqwest;
use serde_json::{self, Value};
use clap::Parser;

#[derive(Parser)]
struct Args {
    #[clap(short, long, help = "Jira project key")]
    project_key: String,
    #[clap(short, long, help = "Jira issue ID")]
    issue_id: String,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = Args::parse();

    // Jira API endpoint for fetching activity
    let url = format!("https://api.atlassian.com/rest/api/3/project/{}/issue/{}/activity", args.project_key, args.issue_id);

    // Authenticate with Jira API (replace with actual authentication logic)
    let auth = ("your_username", "your_password".to_string());
    let client = reqwest::Client::new();

    // Fetch activity from Jira
    let response = client.get(&url).basic_auth(auth.0, Some(auth.1)).send()?;

    if response.status().is_success() {
        let json: Value = serde_json::from_str(&response.text()?)?;
        println!("Activity for issue {}: {:?}", args.issue_id, json);
    } else {
        eprintln!("Failed to fetch activity: {}", response.text()?);
    }

    Ok(())
}