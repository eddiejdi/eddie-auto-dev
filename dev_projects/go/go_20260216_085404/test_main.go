package main_test

import (
	"testing"
)

// TestNewJiraClient tests the NewJiraClient function
func TestNewJiraClient(t *testing.T) {
	client := NewJiraClient("your-jira-api-key")
	if client == nil {
		t.Errorf("NewJiraClient returned nil")
	}
}

// TestCreateIssue tests the CreateIssue function
func TestCreateIssue(t *testing.T) {
	client := NewJiraClient("your-jira-api-key")

	err := client.CreateIssue("New Test Issue", "This is a test issue created by Go Agent.")
	if err != nil {
		t.Errorf("CreateIssue returned error: %v", err)
	}
}

// TestUpdateIssue tests the UpdateIssue function
func TestUpdateIssue(t *testing.T) {
	client := NewJiraClient("your-jira-api-key")

	err := client.UpdateIssue("12345", "Updated Test Issue", "This is an updated test issue.")
	if err != nil {
		t.Errorf("UpdateIssue returned error: %v", err)
	}
}

// TestDeleteIssue tests the DeleteIssue function
func TestDeleteIssue(t *testing.T) {
	client := NewJiraClient("your-jira-api-key")

	err := client.DeleteIssue("12345")
	if err != nil {
		t.Errorf("DeleteIssue returned error: %v", err)
	}
}