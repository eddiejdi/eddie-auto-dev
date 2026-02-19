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

	if client == nil {
		t.Errorf("NewJiraClient returned nil")
	}
}

// TestCreateIssue tests the CreateIssue function.
func TestCreateIssue(t *testing.T) {
	jiraURL := "https://your-jira-instance.atlassian.net"
	username := "your-username"
	password := "your-password"

	client, err := NewJiraClient(jiraURL, username, password)
	if err != nil {
		t.Fatalf("Failed to create Jira client: %v", err)
	}

	projectKey := "YOUR_PROJECT_KEY"
	summary := "New feature request for Go Agent integration"
	description := "Implement Go Agent integration with Jira"

	newIssue, err := client.CreateIssue(projectKey, summary, description)
	if err != nil {
		t.Errorf("Failed to create issue: %v", err)
	}

	if newIssue == nil {
		t.Errorf("CreateIssue returned nil")
	}
}