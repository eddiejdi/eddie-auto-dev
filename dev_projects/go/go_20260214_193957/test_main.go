package main

import (
	"testing"
)

// TestNewJiraClient tests the NewJiraClient function.
func TestNewJiraClient(t *testing.T) {
	jiraURL := "https://your-jira-instance.atlassian.net"
	username := "your-username"
	password := "your-password"

	client, err := NewJiraClient(jiraURL, username, password)
	if err != nil {
		t.Errorf("Failed to create Jira client: %v", err)
	}
}

// TestCreateIssue tests the CreateIssue function.
func TestCreateIssue(t *testing.T) {
	jiraURL := "https://your-jira-instance.atlassian.net"
	username := "your-username"
	password := "your-password"

	client, err := NewJiraClient(jiraURL, username, password)
	if err != nil {
		t.Errorf("Failed to create Jira client: %v", err)
	}

	issueSummary := "New Feature Request"
	issueDescription := "Implement a new feature in the application."

	newIssue, err := client.CreateIssue(issueSummary, issueDescription)
	if err != nil {
		t.Errorf("Failed to create issue: %v", err)
	}
	t.Logf("Created issue with key: %s\n", newIssue.Key)
}

// TestCloseIssue tests the CloseIssue function.
func TestCloseIssue(t *testing.T) {
	jiraURL := "https://your-jira-instance.atlassian.net"
	username := "your-username"
	password := "your-password"

	client, err := NewJiraClient(jiraURL, username, password)
	if err != nil {
		t.Errorf("Failed to create Jira client: %v", err)
	}

	issueKey := "ABC-123"

	err = client.CloseIssue(issueKey)
	if err != nil {
		t.Errorf("Failed to close issue: %v", err)
	}
	t.Logf("Closed the issue with key: %s\n", issueKey)
}