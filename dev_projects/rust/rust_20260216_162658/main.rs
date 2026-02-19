use reqwest;
use serde_json;
use clap::{App, Arg};

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
    status: String,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let app = App::new("Jira Agent")
        .version("1.0")
        .about("Integrates Rust Agent with Jira for tracking activities");

    let matches = app.get_matches();

    let jira_url = matches.value_of("jira_url").unwrap();
    let username = matches.value_of("username").unwrap();
    let password = matches.value_of("password").unwrap();
    let issue_key = matches.value_of("issue_key").unwrap();

    let client = reqwest::Client::new();

    let login_response = client
        .post(format!("{}rest/api/2/session", jira_url))
        .json(&LoginRequest {
            username,
            password,
        })
        .send()
        .await?;

    if !login_response.status().is_success() {
        return Err(login_response.json::<Error>().await.unwrap());
    }

    let login_token = login_response.text().await?;

    let issue_response = client
        .get(format!("{}rest/api/2/issue/{}", jira_url, issue_key))
        .header("Authorization", format!("Bearer {}", login_token))
        .send()
        .await?;

    if !issue_response.status().is_success() {
        return Err(issue_response.json::<Error>().await.unwrap());
    }

    let issue_data = issue_response.text().await?;
    let issue: JiraIssue = serde_json::from_str(&issue_data)?;

    println!("JIRA Issue: {}", issue);

    Ok(())
}

struct LoginRequest {
    username: String,
    password: String,
}