package main

import (
	"testing"
)

// TestNewJiraClient tests the NewJiraClient function
func TestNewJiraClient(t *testing.T) {
	url := "https://your-jira-instance.atlassian.net"
	token := "your-jira-token"

	client, err := NewJiraClient(url, token)
	if err != nil {
		t.Errorf("Failed to create Jira client: %v", err)
	}
}

// TestCreateIssue tests the CreateIssue function
func TestCreateIssue(t *testing.T) {
	url := "https://your-jira-instance.atlassian.net"
	token := "your-jira-token"

	jc, err := NewJiraClient(url, token)
	if err != nil {
		t.Errorf("Failed to create Jira client: %v", err)
	}

	summary := "New feature request"
	description := "Implement a new feature in the application."

	issue, err := jc.CreateIssue(summary, description)
	if err != nil {
		t.Errorf("Failed to create issue: %v", err)
	}
}

// TestCreateIssueError tests the CreateIssue function with an error
func TestCreateIssueError(t *testing.T) {
	url := "https://your-jira-instance.atlassian.net"
	token := "your-jira-token"

	jc, err := NewJiraClient(url, token)
	if err != nil {
		t.Errorf("Failed to create Jira client: %v", err)
	}

	summary := ""
	description := "Implement a new feature in the application."

	issue, err := jc.CreateIssue(summary, description)
	if issue != nil || err == nil {
		t.Errorf("Expected error creating issue, got issue: %v, error: %v", issue, err)
	}
}