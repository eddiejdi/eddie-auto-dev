package main

import (
	"testing"
)

// TestCreateIssue tests the CreateIssue method of GoAgent
func TestCreateIssue(t *testing.T) {
	client := GoAgent{}

	err := client.CreateIssue("New Feature Request", "Implement a new feature in the application")
	if err != nil {
		t.Errorf("Expected no error, got %s", err)
	}
}

// TestUpdateIssue tests the UpdateIssue method of GoAgent
func TestUpdateIssue(t *testing.T) {
	client := GoAgent{}

	err := client.UpdateIssue(123, "Feature Request Updated", "Implement a new feature in the application")
	if err != nil {
		t.Errorf("Expected no error, got %s", err)
	}
}

// TestCreateIssueError tests the CreateIssue method with an error
func TestCreateIssueError(t *testing.T) {
	client := GoAgent{}

	err := client.CreateIssue("", "")
	if err == nil {
		t.Errorf("Expected an error, got none")
	}
}

// TestUpdateIssueError tests the UpdateIssue method with an error
func TestUpdateIssueError(t *testing.T) {
	client := GoAgent{}

	err := client.UpdateIssue(0, "", "")
	if err == nil {
		t.Errorf("Expected an error, got none")
	}
}