package main

import (
	"testing"
)

// JiraClientImpl is a mock implementation of the JiraClient interface for testing purposes
type JiraClientImpl struct{}

func (j *JiraClientImpl) CreateIssue(title, description string) error {
	fmt.Println("Creating issue:", title)
	return nil
}

func (j *JiraClientImpl) UpdateIssue(issueID int, title, description string) error {
	fmt.Println("Updating issue ID", issueID)
	return nil
}

// TestCreateIssue tests the CreateIssue method of GoAgent
func TestCreateIssue(t *testing.T) {
	jiraClient := &JiraClientImpl{}
	goAgent := NewGoAgent(jiraClient)

	err := goAgent.CreateIssue("Test Issue", "This is a test issue.")
	if err != nil {
		t.Errorf("Expected no error, got: %v", err)
	}
}

// TestUpdateIssue tests the UpdateIssue method of GoAgent
func TestUpdateIssue(t *testing.T) {
	jiraClient := &JiraClientImpl{}
	goAgent := NewGoAgent(jiraClient)

	err := goAgent.UpdateIssue(123, "Updated Test Issue", "This is an updated test issue.")
	if err != nil {
		t.Errorf("Expected no error, got: %v", err)
	}
}

// TestCreateIssueError tests the CreateIssue method with an error
func TestCreateIssueError(t *testing.T) {
	jiraClient := &JiraClientImpl{}
	goAgent := NewGoAgent(jiraClient)

	err := goAgent.CreateIssue("", "")
	if err == nil {
		t.Errorf("Expected an error, got: %v", err)
	}
}

// TestUpdateIssueError tests the UpdateIssue method with an error
func TestUpdateIssueError(t *testing.T) {
	jiraClient := &JiraClientImpl{}
	goAgent := NewGoAgent(jiraClient)

	err := goAgent.UpdateIssue(0, "", "")
	if err == nil {
		t.Errorf("Expected an error, got: %v", err)
	}
}