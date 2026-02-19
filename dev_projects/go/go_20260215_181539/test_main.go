package main

import (
	"testing"
)

// TestCreateIssue tests the CreateIssue method of JiraAPI
func TestCreateIssue(t *testing.T) {
	jira := &JiraAPI{}

	title := "Test Issue"
	description := "This is a test issue created by the Go Agent."

	err := jira.CreateIssue(title, description)
	if err != nil {
		t.Errorf("Failed to create issue: %s", err)
	}
}

// TestGetIssues tests the GetIssues method of JiraAPI
func TestGetIssues(t *testing.T) {
	jira := &JiraAPI{}

	title := "Test Issue"
	description := "This is a test issue created by the Go Agent."

	err := jira.CreateIssue(title, description)
	if err != nil {
		t.Errorf("Failed to create issue: %s", err)
	}

	issues, err := jira.GetIssues()
	if err != nil {
		t.Errorf("Failed to get issues: %s", err)
	}

	for _, issue := range issues {
		fmt.Printf("ID: %s, Title: %s\n", issue.ID, issue.Title)
	}
}