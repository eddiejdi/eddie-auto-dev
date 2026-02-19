package main

import (
	"testing"
)

func TestNewJiraClient(t *testing.T) {
	url := "https://your-jira-instance.atlassian.net"
	token := "your-jira-token"

	jiraClient, err := NewJiraClient(url, token)
	if err != nil {
		t.Errorf("Failed to create Jira client: %v", err)
	}
}

func TestCreateIssue(t *testing.T) {
	url := "https://your-jira-instance.atlassian.net"
	token := "your-jira-token"

	jiraClient, err := NewJiraClient(url, token)
	if err != nil {
		t.Errorf("Failed to create Jira client: %v", err)
	}

	title := "Bug in Go Agent integration"
	description := "Go Agent is not working as expected with Jira."

	issue, err := jiraClient.CreateIssue(title, description)
	if err != nil {
		t.Errorf("Failed to create issue: %v", err)
	}
}