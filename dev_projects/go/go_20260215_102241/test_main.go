package main

import (
	"testing"
)

// TestGoAgentClientCreateIssue tests the CreateIssue method of GoAgentClient.
func TestGoAgentClientCreateIssue(t *testing.T) {
	jac := GoAgentClient{}
	err := jac.CreateIssue("Test Issue", "This is a test issue created by Go Agent.")
	if err != nil {
		t.Errorf("Expected no error, got: %v", err)
	}
}

// TestJiraAPICreateIssue tests the CreateIssue method of JiraAPI.
func TestJiraAPICreateIssue(t *testing.T) {
	ja := JiraAPI{}
	err := ja.CreateIssue("Another Test Issue", "This is another test issue created by Jira API.")
	if err != nil {
		t.Errorf("Expected no error, got: %v", err)
	}
}

// TestGoAgentClientCreateIssueError tests the CreateIssue method of GoAgentClient with an error.
func TestGoAgentClientCreateIssueError(t *testing.T) {
	jac := GoAgentClient{}
	err := jac.CreateIssue("", "")
	if err == nil {
		t.Errorf("Expected an error, got: %v", err)
	}
}

// TestJiraAPICreateIssueError tests the CreateIssue method of JiraAPI with an error.
func TestJiraAPICreateIssueError(t *testing.T) {
	ja := JiraAPI{}
	err := ja.CreateIssue("", "")
	if err == nil {
		t.Errorf("Expected an error, got: %v", err)
	}
}

// TestGoAgentClientCreateIssueEdgeCase tests the CreateIssue method of GoAgentClient with edge cases.
func TestGoAgentClientCreateIssueEdgeCase(t *testing.T) {
	jac := GoAgentClient{}
	err := jac.CreateIssue("Test Issue", "")
	if err == nil {
		t.Errorf("Expected an error, got: %v", err)
	}
}

// TestJiraAPICreateIssueEdgeCase tests the CreateIssue method of JiraAPI with edge cases.
func TestJiraAPICreateIssueEdgeCase(t *testing.T) {
	ja := JiraAPI{}
	err := ja.CreateIssue("", "")
	if err == nil {
		t.Errorf("Expected an error, got: %v", err)
	}
}