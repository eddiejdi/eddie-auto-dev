package main

import (
	"testing"
)

type MockJiraClient struct{}

func (m *MockJiraClient) CreateIssue(title string, description string) error {
	if title == "" || description == "" {
		return fmt.Errorf("Title and description cannot be empty")
	}
	return nil
}

func TestNewGoAgent(t *testing.T) {
	jiraClient := NewJiraClient(&MockJiraClient{})
	goAgent := NewGoAgent(jiraClient)
	if goAgent == nil {
		t.Errorf("NewGoAgent should not return nil")
	}
}

func TestCreateIssueSuccess(t *testing.T) {
	jiraClient := &MockJiraClient{}
	goAgent := NewGoAgent(jiraClient)

	title := "New Go Agent Issue"
	description := "This is a test issue created by Go Agent."
	err := goAgent.CreateIssue(title, description)
	if err != nil {
		t.Errorf("CreateIssue should not return an error")
	}
}

func TestCreateIssueError(t *testing.T) {
	jiraClient := &MockJiraClient{}
	goAgent := NewGoAgent(jiraClient)

	title := ""
	description := "This is a test issue created by Go Agent."
	err := goAgent.CreateIssue(title, description)
	if err == nil {
		t.Errorf("CreateIssue should return an error")
	}
}

func TestCreateIssueInvalidTitle(t *testing.T) {
	jiraClient := &MockJiraClient{}
	goAgent := NewGoAgent(jiraClient)

	title := "   "
	description := "This is a test issue created by Go Agent."
	err := goAgent.CreateIssue(title, description)
	if err == nil {
		t.Errorf("CreateIssue should return an error")
	}
}

func TestCreateIssueInvalidDescription(t *testing.T) {
	jiraClient := &MockJiraClient{}
	goAgent := NewGoAgent(jiraClient)

	title := "New Go Agent Issue"
	description := ""
	err := goAgent.CreateIssue(title, description)
	if err == nil {
		t.Errorf("CreateIssue should return an error")
	}
}

func TestCreateIssueEdgeCase(t *testing.T) {
	jiraClient := &MockJiraClient{}
	goAgent := NewGoAgent(jiraClient)

	title := "New Go Agent Issue"
	description := "This is a test issue created by Go Agent."
	err := goAgent.CreateIssue(title, description)
	if err != nil {
		t.Errorf("CreateIssue should not return an error")
	}
}