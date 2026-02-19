package main_test

import (
	"testing"
)

// TestNewJiraClient tests the NewJiraClient function
func TestNewJiraClient(t *testing.T) {
	apiKey := "your-jira-api-key"
	serverURL := "https://your-jira-server.atlassian.net"

	jiraClient, err := NewJiraClient(apiKey, serverURL)
	if err != nil {
		t.Errorf("Failed to create Jira client: %v", err)
	}
}

// TestCreateIssue tests the CreateIssue function
func TestCreateIssue(t *testing.T) {
	apiKey := "your-jira-api-key"
	serverURL := "https://your-jira-server.atlassian.net"

	jiraClient, err := NewJiraClient(apiKey, serverURL)
	if err != nil {
		t.Errorf("Failed to create Jira client: %v", err)
	}

	summary := "Test issue created by Go Agent"
	description := "This is a test issue created using Go Agent."

	newIssue, err := jiraClient.CreateIssue(summary, description)
	if err != nil {
		t.Errorf("Failed to create issue: %v", err)
	}
}