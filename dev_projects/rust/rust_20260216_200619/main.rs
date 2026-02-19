use reqwest;
use serde_json::Value;

#[derive(Debug)]
struct JiraIssue {
    id: String,
    key: String,
    summary: String,
    status: String,
}

impl JiraIssue {
    fn from_response(response: &reqwest::Response) -> Result<Self, reqwest::Error> {
        let body = response.text()?;
        Ok serde_json::from_str(&body)?
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Configuração do Jira
    let jira_url = "https://your-jira-instance.atlassian.net/rest/api/2";
    let username = "your-username";
    let password = "your-password";

    // Conecta ao Jira
    let client = reqwest::Client::new();
    let auth = reqwest::basic_auth(username, Some(password));

    // Listar issues
    let response = client.get(format!("{}/issue", jira_url))
        .auth(auth)
        .send()
        .await?;

    if !response.status().is_success() {
        return Err(Box::new(reqwest::Error::from(response)));
    }

    let issues: Vec<JiraIssue> = response.json().await?;
    println!("Issues in Jira:");
    for issue in issues {
        println!("{:?}", issue);
    }

    Ok(())
}