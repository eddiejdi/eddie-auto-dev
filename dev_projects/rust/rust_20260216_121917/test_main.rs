use std::fs;
use std::io::{self, Write};
use serde_json;

// Define a struct to represent an issue in Jira
#[derive(Deserialize)]
struct Issue {
    key: String,
    summary: String,
    status: String,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Read the JSON data from the file
    let file_path = "issues.json";
    if !fs::path_exists(file_path) {
        return Err("File not found".into());
    }

    let mut file = fs::File::open(file_path)?;
    let mut content = String::new();
    io::read_to_string(&mut file, &mut content)?;

    // Parse the JSON data into a vector of Issue structs
    let issues: Vec<Issue> = serde_json::from_str(&content)?;

    // Print the issue summary for each issue
    for issue in issues {
        println!("Key: {}, Summary: {}", issue.key, issue.summary);
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_read_file() -> Result<(), Box<dyn std::error::Error>> {
        let file_path = "issues.json";
        if !fs::path_exists(file_path) {
            return Err("File not found".into());
        }

        let mut file = fs::File::open(file_path)?;
        let mut content = String::new();
        io::read_to_string(&mut file, &mut content)?;

        // Parse the JSON data into a vector of Issue structs
        let issues: Vec<Issue> = serde_json::from_str(&content)?;

        assert_eq!(issues.len(), 0); // Edge case: empty file

        Ok(())
    }

    #[test]
    fn test_parse_json() -> Result<(), Box<dyn std::error::Error>> {
        let json_data = r#"[{"key": "JIRA-1", "summary": "Bug in login page", "status": "Open"}]"#;
        let issues: Vec<Issue> = serde_json::from_str(json_data)?;

        assert_eq!(issues.len(), 1);
        assert_eq!(issues[0].key, "JIRA-1");
        assert_eq!(issues[0].summary, "Bug in login page");
        assert_eq!(issues[0].status, "Open");

        Ok(())
    }

    #[test]
    fn test_print_issues() -> Result<(), Box<dyn std::error::Error>> {
        let issues = vec![
            Issue { key: "JIRA-1".to_string(), summary: "Bug in login page".to_string(), status: "Open" },
            Issue { key: "JIRA-2".to_string(), summary: "Feature request for new dashboard".to_string(), status: "In Progress" },
        ];

        println!("Issues:");
        for issue in issues {
            println!("Key: {}, Summary: {}", issue.key, issue.summary);
        }

        Ok(())
    }
}