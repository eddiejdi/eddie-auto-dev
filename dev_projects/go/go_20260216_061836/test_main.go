package main_test

import (
	"testing"
)

// Teste para criar um novo issue com valores válidos
func TestCreateIssueValid(t *testing.T) {
	jiraClient := &LocalJiraClient{}
	goAgent := NewGoAgent(jiraClient)
	err := goAgent.CreateIssue("New Test Issue", "This is a test issue created by Go Agent")
	if err != nil {
		t.Errorf("Failed to create issue: %v", err)
	}
}

// Teste para criar um novo issue com valores inválidos
func TestCreateIssueInvalid(t *testing.T) {
	jiraClient := &LocalJiraClient{}
	goAgent := NewGoAgent(jiraClient)
	err := goAgent.CreateIssue("", "")
	if err == nil {
		t.Errorf("Expected an error for empty title and description")
	}
}

// Teste para criar um novo issue com valores limite
func TestCreateIssueLimit(t *testing.T) {
	jiraClient := &LocalJiraClient{}
	goAgent := NewGoAgent(jiraClient)
	err := goAgent.CreateIssue("This is a very long title that exceeds the limit", "This is a test issue created by Go Agent")
	if err == nil {
		t.Errorf("Expected an error for too long title")
	}
}

// Teste para criar um novo issue com valores vazios
func TestCreateIssueEmpty(t *testing.T) {
	jiraClient := &LocalJiraClient{}
	goAgent := NewGoAgent(jiraClient)
	err := goAgent.CreateIssue("", "This is a test issue created by Go Agent")
	if err == nil {
		t.Errorf("Expected an error for empty title")
	}
}

// Teste para criar um novo issue com valores nulos
func TestCreateIssueNull(t *testing.T) {
	jiraClient := &LocalJiraClient{}
	goAgent := NewGoAgent(jiraClient)
	err := goAgent.CreateIssue(nil, "This is a test issue created by Go Agent")
	if err == nil {
		t.Errorf("Expected an error for null title")
	}
}

// Teste para criar um novo issue com valores None
func TestCreateIssueNone(t *testing.T) {
	jiraClient := &LocalJiraClient{}
	goAgent := NewGoAgent(jiraClient)
	err := goAgent.CreateIssue(None, "This is a test issue created by Go Agent")
	if err == nil {
		t.Errorf("Expected an error for None title")
	}
}