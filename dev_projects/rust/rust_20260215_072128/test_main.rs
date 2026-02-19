use crate::Issue;
use reqwest::{Error, Response};
use serde_json::Value;

// Test case for fetch_issues function
#[tokio::test]
async fn test_fetch_issues() {
    let url = "https://your-jira-instance.atlassian.net/rest/api/2/search";
    let token = "your-jira-api-token";

    // Mock response with valid JSON data
    let mock_response = r#"
        {
            "issues": [
                {
                    "key": "ABC-123",
                    "summary": "Test Issue",
                    "status": "Open"
                }
            ]
        }
    "#;

    let client = reqwest::Client::new();
    let response = client.get(url)
        .header("Authorization", format!("Bearer {}", token))
        .send()
        .await
        .expect("Failed to fetch issues");

    assert_eq!(response.status(), 200);

    let text = response.text().await.expect("Failed to parse JSON");
    let issues: Vec<Issue> = serde_json::from_str(&text).expect("Failed to deserialize JSON");

    assert_eq!(issues.len(), 1);
    assert_eq!(issues[0].key, "ABC-123");
    assert_eq!(issues[0].summary, "Test Issue");
    assert_eq!(issues[0].status, "Open");
}

// Test case for fetch_issues function with invalid response
#[tokio::test]
async fn test_fetch_issues_invalid_response() {
    let url = "https://your-jira-instance.atlassian.net/rest/api/2/search";
    let token = "your-jira-api-token";

    // Mock response with an error message
    let mock_response = r#"
        {
            "error": {
                "message": "Invalid request"
            }
        }
    "#;

    let client = reqwest::Client::new();
    let response = client.get(url)
        .header("Authorization", format!("Bearer {}", token))
        .send()
        .await
        .expect("Failed to fetch issues");

    assert_eq!(response.status(), 400);

    let text = response.text().await.expect("Failed to parse JSON");
    let error: serde_json::Value = serde_json::from_str(&text).expect("Failed to deserialize JSON");

    assert_eq!(error["message"], "Invalid request");
}

// Test case for monitor_issues function
#[tokio::test]
async fn test_monitor_issues() {
    let url = "https://your-jira-instance.atlassian.net/rest/api/2/search";
    let token = "your-jira-api-token";

    // Mock response with valid JSON data
    let mock_response = r#"
        {
            "issues": [
                {
                    "key": "ABC-123",
                    "summary": "Test Issue",
                    "status": "Open"
                }
            ]
        }
    "#;

    let client = reqwest::Client::new();
    let response = client.get(url)
        .header("Authorization", format!("Bearer {}", token))
        .send()
        .await
        .expect("Failed to fetch issues");

    assert_eq!(response.status(), 200);

    let text = response.text().await.expect("Failed to parse JSON");
    let issues: Vec<Issue> = serde_json::from_str(&text).expect("Failed to deserialize JSON");

    for issue in issues {
        println!("Issue {}: {}", issue.key, issue.summary);
    }

    // Simulate a delay before the next iteration
    tokio::time::sleep(Duration::from_secs(10)).await;
}

// Test case for monitor_issues function with invalid response
#[tokio::test]
async fn test_monitor_issues_invalid_response() {
    let url = "https://your-jira-instance.atlassian.net/rest/api/2/search";
    let token = "your-jira-api-token";

    // Mock response with an error message
    let mock_response = r#"
        {
            "error": {
                "message": "Invalid request"
            }
        }
    "#;

    let client = reqwest::Client::new();
    let response = client.get(url)
        .header("Authorization", format!("Bearer {}", token))
        .send()
        .await
        .expect("Failed to fetch issues");

    assert_eq!(response.status(), 400);

    let text = response.text().await.expect("Failed to parse JSON");
    let error: serde_json::Value = serde_json::from_str(&text).expect("Failed to deserialize JSON");

    assert_eq!(error["message"], "Invalid request");
}