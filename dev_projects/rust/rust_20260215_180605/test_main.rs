use std::io::{self, Write};
use serde_json::Value;

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
    status: String,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Simulação de dados do Jira
    let jira_issues = vec![
        JiraIssue {
            key: "ABC-123".to_string(),
            summary: "Bug na página inicial".to_string(),
            status: "Open".to_string(),
        },
        JiraIssue {
            key: "XYZ-456".to_string(),
            summary: "Funcionalidade não funciona".to_string(),
            status: "In Progress".to_string(),
        },
    ];

    // Simulação de envio para o servidor
    let mut writer = io::stdout();
    for issue in &jira_issues {
        writeln!(
            &mut writer,
            r#"{{"key": "{}", "summary": "{}", "status": "{}"}}"#,
            issue.key, issue.summary, issue.status
        )?;
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_main() -> Result<(), Box<dyn std::error::Error>> {
        let jira_issues = vec![
            JiraIssue {
                key: "ABC-123".to_string(),
                summary: "Bug na página inicial".to_string(),
                status: "Open".to_string(),
            },
            JiraIssue {
                key: "XYZ-456".to_string(),
                summary: "Funcionalidade não funciona".to_string(),
                status: "In Progress".to_string(),
            },
        ];

        let mut writer = io::stdout();
        for issue in &jira_issues {
            writeln!(
                &mut writer,
                r#"{{"key": "{}", "summary": "{}", "status": "{}"}}"#,
                issue.key, issue.summary, issue.status
            )?;
        }

        Ok(())
    }
}