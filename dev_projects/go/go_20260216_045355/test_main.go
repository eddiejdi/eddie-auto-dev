package main

import (
	"testing"
)

// MockJiraClient is a mock implementation of JiraClient for testing purposes
type MockJiraClient struct{}

func (m *MockJiraClient) CreateIssue(title string, description string) error {
	if title == "" || description == "" {
		return fmt.Errorf("Title and description cannot be empty")
	}
	return nil
}

func (m *MockJiraClient) UpdateIssue(issueID int, title string, description string) error {
	if issueID < 1 {
		return fmt.Errorf("Invalid issue ID")
	}
	if title == "" || description == "" {
		return fmt.Errorf("Title and description cannot be empty")
	}
	return nil
}

// TestCreateIssue tests the CreateIssue method of GoAgent
func TestCreateIssue(t *testing.T) {
	client := NewJiraClient(&MockJiraClient{})
	ga := NewGoAgent(client)

	err := ga.CreateIssue("Test Issue", "This is a test issue.")
	if err != nil {
		t.Errorf("Expected no error, got %v", err)
	}
}

// TestUpdateIssue tests the UpdateIssue method of GoAgent
func TestUpdateIssue(t *testing.T) {
	client := NewJiraClient(&MockJiraClient{})
	ga := NewGoAgent(client)

	err := ga.UpdateIssue(1, "Updated Test Issue", "This is an updated test issue.")
	if err != nil {
		t.Errorf("Expected no error, got %v", err)
	}
}

// TestCreateIssueWithInvalidTitle tests the CreateIssue method with an invalid title
func TestCreateIssueWithInvalidTitle(t *testing.T) {
	client := NewJiraClient(&MockJiraClient{})
	ga := NewGoAgent(client)

	err := ga.CreateIssue("", "This is a test issue.")
	if err == nil {
		t.Errorf("Expected error, got no error")
	}
}

// TestCreateIssueWithInvalidDescription tests the CreateIssue method with an invalid description
func TestCreateIssueWithInvalidDescription(t *testing.T) {
	client := NewJiraClient(&MockJiraClient{})
	ga := NewGoAgent(client)

	err := ga.CreateIssue("Test Issue", "")
	if err == nil {
		t.Errorf("Expected error, got no error")
	}
}

// TestUpdateIssueWithInvalidID tests the UpdateIssue method with an invalid issue ID
func TestUpdateIssueWithInvalidID(t *testing.T) {
	client := NewJiraClient(&MockJiraClient{})
	ga := NewGoAgent(client)

	err := ga.UpdateIssue(0, "Updated Test Issue", "This is an updated test issue.")
	if err == nil {
		t.Errorf("Expected error, got no error")
	}
}

// TestUpdateIssueWithInvalidTitle tests the UpdateIssue method with an invalid title
func TestUpdateIssueWithInvalidTitle(t *testing.T) {
	client := NewJiraClient(&MockJiraClient{})
	ga := NewGoAgent(client)

	err := ga.UpdateIssue(1, "", "This is an updated test issue.")
	if err == nil {
		t.Errorf("Expected error, got no error")
	}
}

// TestUpdateIssueWithInvalidDescription tests the UpdateIssue method with an invalid description
func TestUpdateIssueWithInvalidDescription(t *testing.T) {
	client := NewJiraClient(&MockJiraClient{})
	ga := NewGoAgent(client)

	err := ga.UpdateIssue(1, "Updated Test Issue", "")
	if err == nil {
		t.Errorf("Expected error, got no error")
	}
}