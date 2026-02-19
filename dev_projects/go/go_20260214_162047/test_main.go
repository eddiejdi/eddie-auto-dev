package main

import (
	"testing"
)

// TestJiraClientCreateIssue tests the CreateIssue method of JiraClient
func TestJiraClientCreateIssue(t *testing.T) {
	jc := NewJiraClient("your-jira-token")
	err := jc.CreateIssue("New Feature Request", "Implement a new feature in the application")
	if err != nil {
		t.Errorf("Error creating issue: %v", err)
	}
}

// TestJiraClientUpdateIssue tests the UpdateIssue method of JiraClient
func TestJiraClientUpdateIssue(t *testing.T) {
	jc := NewJiraClient("your-jira-token")
	err := jc.UpdateIssue("JIRA-123", "Feature Implemented", "The new feature has been successfully implemented.")
	if err != nil {
		t.Errorf("Error updating issue: %v", err)
	}
}

// TestJiraClientCreateIssueWithError tests the CreateIssue method with an error
func TestJiraClientCreateIssueWithError(t *testing.T) {
	jc := NewJiraClient("")
	err := jc.CreateIssue("New Feature Request", "Implement a new feature in the application")
	if err == nil {
		t.Errorf("Expected an error, but got none")
	}
}

// TestJiraClientUpdateIssueWithError tests the UpdateIssue method with an error
func TestJiraClientUpdateIssueWithError(t *testing.T) {
	jc := NewJiraClient("")
	err := jc.UpdateIssue("JIRA-123", "Feature Implemented", "")
	if err == nil {
		t.Errorf("Expected an error, but got none")
	}
}

// TestJiraClientCreateIssueWithInvalidToken tests the CreateIssue method with an invalid token
func TestJiraClientCreateIssueWithInvalidToken(t *testing.T) {
	jc := NewJiraClient("")
	err := jc.CreateIssue("New Feature Request", "Implement a new feature in the application")
	if err == nil {
		t.Errorf("Expected an error, but got none")
	}
}

// TestJiraClientUpdateIssueWithInvalidToken tests the UpdateIssue method with an invalid token
func TestJiraClientUpdateIssueWithInvalidToken(t *testing.T) {
	jc := NewJiraClient("")
	err := jc.UpdateIssue("JIRA-123", "Feature Implemented", "")
	if err == nil {
		t.Errorf("Expected an error, but got none")
	}
}