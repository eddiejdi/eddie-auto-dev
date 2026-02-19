use reqwest;
use serde_json;
use clap::Parser;

#[derive(Parser)]
struct Args {
    #[clap(long, short, default_value = "http://localhost:8080")]
    jira_url: String,
    #[clap(long, short, default_value = "my_project")]
    project_key: String,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = Args::parse();

    // Simulação de uma atividade
    let activity = Activity {
        key: "ACT-123",
        name: "Rust Agent Integration",
        status: "In Progress",
    };

    // Enviar a atividade para Jira
    send_activity_to_jira(&args.jira_url, &args.project_key, &activity)?;

    Ok(())
}

struct Activity {
    key: String,
    name: String,
    status: String,
}

fn send_activity_to_jira(jira_url: &str, project_key: &str, activity: &Activity) -> Result<(), Box<dyn std::error::Error>> {
    let url = format!("{}rest/api/2/issue/{}/comment", jira_url, activity.key);

    let headers = reqwest::header::HeaderMap::from([
        ("Content-Type".to_string(), "application/json".to_string()),
    ]);

    let body = serde_json::json!({
        "body": {
            "type": "doc",
            "content": [
                {
                    "text": activity.name
                },
                {
                    "text": "Status: " + &activity.status
                }
            ]
        }
    });

    let response = reqwest::Client::new()
        .post(url)
        .headers(headers)
        .json(&body)
        .send()?;

    if response.status().is_success() {
        println!("Activity sent to Jira successfully");
    } else {
        let error_message = response.text()?;
        eprintln!("Failed to send activity to Jira: {}", error_message);
    }

    Ok(())
}