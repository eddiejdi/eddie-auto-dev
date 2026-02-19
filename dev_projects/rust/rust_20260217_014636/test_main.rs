use reqwest;
use serde_json::Value;

struct JiraClient {
    url: String,
    token: String,
}

impl JiraClient {
    fn new(url: &str, token: &str) -> Self {
        JiraClient {
            url: url.to_string(),
            token: token.to_string(),
        }
    }

    async fn create_issue(&self, issue_data: Value) -> Result<String, reqwest::Error> {
        let response = self
            .client()
            .post(format!("{}rest/api/2/issue", &self.url))
            .header("Authorization", format!("Basic {}", base64::encode(&format!(":{}:", self.token))))
            .json(issue_data)
            .send()
            .await?;

        if response.status().is_success() {
            let json = response.json::<Value>().await?;
            Ok(json["id"].as_str().unwrap().to_string())
        } else {
            Err(reqwest::Error::from(response))
        }
    }

    fn client(&self) -> reqwest::Client {
        reqwest::Client::new()
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira_client = JiraClient::new("https://your-jira-instance.atlassian.net", "your-api-token");

    // Teste de sucesso com valores válidos
    let issue_data = json!({
        "fields": {
            "project": { "key": "YOUR-PROJECT" },
            "summary": "Test Issue",
            "description": "This is a test issue created by Rust Agent",
            "issuetype": { "name": "Bug" }
        }
    });

    let issue_id = jira_client.create_issue(issue_data).await?;
    println!("Issue created with ID: {}", issue_id);

    // Teste de erro (divisão por zero)
    let invalid_number = 0.0;
    let issue_data_with_zero = json!({
        "fields": {
            "project": { "key": "YOUR-PROJECT" },
            "summary": "Test Issue",
            "description": "This is a test issue created by Rust Agent",
            "issuetype": { "name": "Bug" }
        }
    });

    match jira_client.create_issue(issue_data_with_zero).await {
        Ok(_) => panic!("Expected an error but got success"),
        Err(e) => assert_eq!(e.status(), reqwest::StatusCode::BAD_REQUEST),
    }

    // Teste de erro (valores inválidos)
    let invalid_project_key = "INVALID-PROJECT";
    let issue_data_with_invalid_project_key = json!({
        "fields": {
            "project": { "key": invalid_project_key },
            "summary": "Test Issue",
            "description": "This is a test issue created by Rust Agent",
            "issuetype": { "name": "Bug" }
        }
    });

    match jira_client.create_issue(issue_data_with_invalid_project_key).await {
        Ok(_) => panic!("Expected an error but got success"),
        Err(e) => assert_eq!(e.status(), reqwest::StatusCode::BAD_REQUEST),
    }

    // Teste de edge case (valores limite)
    let large_number = 1000000.0;
    let issue_data_with_large_number = json!({
        "fields": {
            "project": { "key": "YOUR-PROJECT" },
            "summary": "Test Issue",
            "description": "This is a test issue created by Rust Agent",
            "issuetype": { "name": "Bug" }
        }
    });

    let issue_id = jira_client.create_issue(issue_data_with_large_number).await?;
    println!("Issue created with ID: {}", issue_id);

    // Teste de edge case (string vazia)
    let empty_string = "";
    let issue_data_with_empty_string = json!({
        "fields": {
            "project": { "key": "YOUR-PROJECT" },
            "summary": empty_string,
            "description": "This is a test issue created by Rust Agent",
            "issuetype": { "name": "Bug" }
        }
    });

    match jira_client.create_issue(issue_data_with_empty_string).await {
        Ok(_) => panic!("Expected an error but got success"),
        Err(e) => assert_eq!(e.status(), reqwest::StatusCode::BAD_REQUEST),
    }

    // Teste de edge case (None)
    let none_value = None;
    let issue_data_with_none_value = json!({
        "fields": {
            "project": { "key": "YOUR-PROJECT" },
            "summary": "Test Issue",
            "description": "This is a test issue created by Rust Agent",
            "issuetype": { "name": "Bug" }
        }
    });

    match jira_client.create_issue(issue_data_with_none_value).await {
        Ok(_) => panic!("Expected an error but got success"),
        Err(e) => assert_eq!(e.status(), reqwest::StatusCode::BAD_REQUEST),
    }

    Ok(())
}