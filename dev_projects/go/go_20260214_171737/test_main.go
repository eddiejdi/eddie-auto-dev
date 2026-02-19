package main

import (
	"testing"
)

// TestNewJiraClient tests the NewJiraClient function
func TestNewJiraClient(t *testing.T) {
	url := "https://your-jira-instance.atlassian.net"
	token := "YOUR_JIRA_TOKEN"

	jc, err := NewJiraClient(url, token)
	if err != nil {
		t.Errorf("Failed to create Jira client: %v", err)
	}
}

// TestCreateIssue tests the CreateIssue function
func TestCreateIssue(t *testing.T) {
	url := "https://your-jira-instance.atlassian.net"
	token := "YOUR_JIRA_TOKEN"

	jc, err := NewJiraClient(url, token)
	if err != nil {
		t.Errorf("Failed to create Jira client: %v", err)
	}

	summary := "New feature request"
	description := "Implement a new feature that allows users to search for products."

	newIssue, err := jc.CreateIssue(summary, description)
	if err != nil {
		t.Errorf("Failed to create issue: %v", err)
	}
}