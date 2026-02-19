package main

import (
	"testing"
)

// TestNewJiraClient tests the NewJiraClient function
func TestNewJiraClient(t *testing.T) {
	url := "https://your-jira-instance.atlassian.net"
	token := "your-jira-token"

	jiraClient, err := NewJiraClient(url, token)
	if err != nil {
		t.Errorf("Failed to create Jira client: %v", err)
	}
}

// TestCreateIssue tests the CreateIssue function
func TestCreateIssue(t *testing.T) {
	url := "https://your-jira-instance.atlassian.net"
	token := "your-jira-token"

	jiraClient, err := NewJiraClient(url, token)
	if err != nil {
		t.Errorf("Failed to create Jira client: %v", err)
	}

	issue, err := jiraClient.CreateIssue("New Task", "This is a new task for the project.")
	if err != nil {
		t.Errorf("Failed to create issue: %v", err)
	}
}

// TestMonitorIssues tests the MonitorIssues function
func TestMonitorIssues(t *testing.T) {
	url := "https://your-jira-instance.atlassian.net"
	token := "your-jira-token"

	jiraClient, err := NewJiraClient(url, token)
	if err != nil {
		t.Errorf("Failed to create Jira client: %v", err)
	}

	go jiraClient.MonitorIssues()
}