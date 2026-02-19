package main_test

import (
	"testing"
	"github.com/go-jira/jira/v5"
)

// TestNewJiraClient tests the NewJiraClient function.
func TestNewJiraClient(t *testing.T) {
	username := "your-jira-username"
	password := "your-jira-password"

	client, err := NewJiraClient(username, password)
	if err != nil {
		t.Errorf("Failed to create Jira client: %v", err)
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

	summary := "New Test Issue"
	description := "This is a test issue created by Go Agent."
	issue, err := jc.CreateIssue(summary, description)
	if err != nil {
		t.Errorf("Failed to create issue: %v", err)
	}
	fmt.Printf("Created issue with ID: %s\n", issue.Key)
}

// TestCreateIssueEdgeCases tests the CreateIssue function with edge cases.
func TestCreateIssueEdgeCases(t *testing.T) {
	username := "your-jira-username"
	password := "your-jira-password"

	jc, err := NewJiraClient(username, password)
	if err != nil {
		t.Fatalf("Failed to create Jira client: %v", err)
	}

	summary := ""
	description := "This is a test issue created by Go Agent."
	issue, err := jc.CreateIssue(summary, description)
	if err == nil {
		t.Errorf("Expected error for empty summary")
	}

	summary = "New Test Issue"
	description = ""
	issue, err = jc.CreateIssue(summary, description)
	if err == nil {
		t.Errorf("Expected error for empty description")
	}
}