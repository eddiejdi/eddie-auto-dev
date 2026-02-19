use std::error::Error;
use tokio::net::TcpStream;
use serde_json::{to_string, from_str};

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
    description: String,
}

async fn connect_to_jira(server_url: &str) -> Result<TcpStream, Box<dyn Error>> {
    let mut stream = TcpStream::connect(server_url)?;
    Ok(stream)
}

async fn send_issue_to_jira(issue: JiraIssue, stream: &mut TcpStream) -> Result<(), Box<dyn Error>> {
    let issue_json = to_string(&issue)?;
    stream.write_all(issue_json.as_bytes())?;
    Ok(())
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let server_url = "http://localhost:8080";
    let issue_key = "JIRA-1234";
    let summary = "Bug in Rust Agent";
    let description = "The Rust Agent is not working as expected.";

    let mut stream = connect_to_jira(server_url).await?;
    let issue = JiraIssue {
        key: issue_key.to_string(),
        summary,
        description,
    };

    send_issue_to_jira(issue, &mut stream).await?;

    println!("Issue sent to Jira successfully!");

    Ok(())
}

#[tokio::test]
async fn test_connect_to_jira_success() {
    let server_url = "http://localhost:8080";
    let result = connect_to_jira(server_url).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_send_issue_to_jira_success() {
    let server_url = "http://localhost:8080";
    let mut stream = connect_to_jira(server_url).await.unwrap();
    let issue_key = "JIRA-1234";
    let summary = "Bug in Rust Agent";
    let description = "The Rust Agent is not working as expected.";

    let issue = JiraIssue {
        key: issue_key.to_string(),
        summary,
        description,
    };

    send_issue_to_jira(issue, &mut stream).await.unwrap();
}

#[tokio::test]
async fn test_send_issue_to_jira_failure() {
    let server_url = "http://localhost:8080";
    let mut stream = connect_to_jira(server_url).await.unwrap();
    let issue_key = "JIRA-1234";
    let summary = "Bug in Rust Agent";
    let description = "The Rust Agent is not working as expected.";

    let issue = JiraIssue {
        key: issue_key.to_string(),
        summary,
        description,
    };

    send_issue_to_jira(issue, &mut stream).await.unwrap_err();
}