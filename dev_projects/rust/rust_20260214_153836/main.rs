use reqwest;
use serde_json::{self, Value};
use tokio::sync::mpsc;

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
    status: String,
}

async fn fetch_jira_issue(jira_key: &str) -> Result<JiraIssue, reqwest::Error> {
    let url = format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}", jira_key);
    let response = reqwest::get(&url).await?;
    if response.status().is_success() {
        let json: Value = serde_json::from_str(&response.text().await?)?;
        Ok(JiraIssue {
            key: json["key"].as_str().unwrap().to_string(),
            summary: json["fields"]["summary"].as_str().unwrap().to_string(),
            status: json["fields"]["status"]["name"].as_str().unwrap().to_string(),
        })
    } else {
        Err(reqwest::Error::from(response.status()))
    }
}

async fn monitor_jira_issues(jira_key: &str, mut sender: mpsc::Sender<JiraIssue>) {
    loop {
        let issue = fetch_jira_issue(jira_key).await;
        if let Ok(issue) = issue {
            sender.send(issue).await.unwrap();
        } else {
            println!("Failed to fetch issue for key {}", jira_key);
        }
        tokio::time::sleep(tokio::time::Duration::from_secs(10)).await;
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let (sender, receiver) = mpsc::channel(10);

    let jira_key = "YOUR_JIRA_KEY";
    tokio::spawn(monitor_jira_issues(jira_key, sender));

    while let Some(issue) = receiver.recv().await {
        println!("Issue: {:?}", issue);
    }

    Ok(())
}