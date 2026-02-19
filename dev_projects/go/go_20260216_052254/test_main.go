package main

import (
	"testing"
)

// TestCreateIssue tests the CreateIssue method of JiraClient
func TestCreateIssue(t *testing.T) {
	jira := &JiraClient{}
	err := jira.CreateIssue("Bug Fix", "Fixes the login page")
	if err != nil {
		t.Errorf("Expected no error, got %v", err)
	}
}

// TestUpdateIssue tests the UpdateIssue method of JiraClient
func TestUpdateIssue(t *testing.T) {
	jira := &JiraClient{}
	err := jira.UpdateIssue(1, "New Feature", "Adds a new feature to the application")
	if err != nil {
		t.Errorf("Expected no error, got %v", err)
	}
}

// TestDeleteIssue tests the DeleteIssue method of JiraClient
func TestDeleteIssue(t *testing.T) {
	jira := &JiraClient{}
	err := jira.DeleteIssue(2)
	if err != nil {
		t.Errorf("Expected no error, got %v", err)
	}
}