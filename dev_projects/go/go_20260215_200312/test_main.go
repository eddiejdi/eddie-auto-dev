package main

import (
	"testing"
)

// TestCreateIssue tests the CreateIssue method of GoAgent
func TestCreateIssue(t *testing.T) {
	jiraClient := &GoAgent{}

	err := jiraClient.CreateIssue("New Feature Request", "Implement a new feature to improve the user experience")
	if err != nil {
		t.Errorf("Expected no error, got: %v", err)
	}
}

// TestUpdateIssue tests the UpdateIssue method of GoAgent
func TestUpdateIssue(t *testing.T) {
	jiraClient := &GoAgent{}

	err := jiraClient.UpdateIssue(1, "Feature Request Updated", "Now the feature is fully implemented")
	if err != nil {
		t.Errorf("Expected no error, got: %v", err)
	}
}

// TestCreateIssueError tests the CreateIssue method with an error
func TestCreateIssueError(t *testing.T) {
	jiraClient := &GoAgent{}

	err := jiraClient.CreateIssue("", "")
	if err == nil {
		t.Errorf("Expected an error, got: %v", err)
	}
}

// TestUpdateIssueError tests the UpdateIssue method with an error
func TestUpdateIssueError(t *testing.T) {
	jiraClient := &GoAgent{}

	err := jiraClient.UpdateIssue(0, "", "")
	if err == nil {
		t.Errorf("Expected an error, got: %v", err)
	}
}