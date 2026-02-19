package main

import (
	"testing"
)

// TestNewJiraClient tests the NewJiraClient function.
func TestNewJiraClient(t *testing.T) {
	username := "your-jira-username"
	password := "your-jira-password"

	jc, err := NewJiraClient(username, password)
	if err != nil {
		t.Errorf("Failed to create Jira client: %v", err)
	}

	if jc.client == nil {
		t.Errorf("NewJiraClient returned a nil client")
	}
}

// TestCreateIssue tests the CreateIssue function.
func TestCreateIssue(t *testing.T) {
	username := "your-jira-username"
	password := "your-jira-password"

	jc, err := NewJiraClient(username, password)
	if err != nil {
		t.Fatalf("Failed to create Jira client: %v", err)
	}

	title := "New Feature Request"
	description := "Implement a new feature in the application."

	newIssue, err := jc.CreateIssue(title, description)
	if err != nil {
		t.Errorf("CreateIssue failed: %v", err)
	}

	if newIssue == nil {
		t.Errorf("CreateIssue returned a nil issue")
	}
}