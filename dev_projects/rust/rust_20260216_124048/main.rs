use reqwest;
use serde_json;

#[derive(Debug, Serialize)]
struct JiraIssue {
    key: String,
    fields: Fields,
}

#[derive(Debug, Serialize)]
struct Fields {
    summary: String,
    description: String,
    assignee: Option<String>,
    priority: Priority,
    status: Status,
}

#[derive(Debug, Serialize)]
struct Priority {
    name: String,
}

#[derive(Debug, Serialize)]
struct Status {
    name: String,
}

async fn create_jira_issue(jira_url: &str, issue: JiraIssue) -> Result<(), reqwest::Error> {
    let response = reqwest::Client::new()
        .post(jira_url)
        .json(&issue)
        .send()
        .await?;

    if response.status().is_success() {
        Ok(())
    } else {
        Err(reqwest::Error::from(response))
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira_url = "https://your-jira-instance.atlassian.net/rest/api/2/issue";
    let issue_key = "YOUR-ISSUE-KEY";
    let summary = "Rust Agent Integration Test";
    let description = "This is a test for integrating Rust Agent with Jira.";
    let assignee = Some("user123");
    let priority_name = "High";
    let status_name = "In Progress";

    let priority = Priority {
        name: priority_name.to_string(),
    };

    let status = Status {
        name: status_name.to_string(),
    };

    let fields = Fields {
        summary,
        description,
        assignee,
        priority,
        status,
    };

    let issue = JiraIssue {
        key: issue_key.to_string(),
        fields,
    };

    create_jira_issue(jira_url, issue).await?;

    println!("Jira issue created successfully.");

    Ok(())
}