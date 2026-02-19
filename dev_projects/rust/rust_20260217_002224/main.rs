use std::fs;
use std::io::{self, BufRead};
use std::path::Path;

// Define a struct to represent an issue in Jira
struct Issue {
    id: String,
    title: String,
    description: String,
}

// Function to parse issues from a CSV file
fn read_issues_from_csv(file_path: &str) -> Result<Vec<Issue>, io::Error> {
    let file = fs::File::open(file_path)?;
    let reader = BufReader::new(file);

    let mut issues = Vec::new();

    for line in reader.lines() {
        let line = line?;
        let fields: Vec<&str> = line.split(',').collect();
        if fields.len() == 3 {
            issues.push(Issue {
                id: fields[0].to_string(),
                title: fields[1].to_string(),
                description: fields[2].to_string(),
            });
        }
    }

    Ok(issues)
}

// Function to create an issue in Jira
fn create_issue(issue: &Issue) -> Result<(), Box<dyn std::error::Error>> {
    // Simulate creating an issue in Jira
    println!("Creating issue: {}", issue.title);
    Ok(())
}

// Main function for the CLI application
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let file_path = "issues.csv";
    if !Path::new(file_path).exists() {
        return Err("Issues CSV file not found".into());
    }

    let issues = read_issues_from_csv(file_path)?;
    for issue in &issues {
        create_issue(issue)?;
    }

    Ok(())
}