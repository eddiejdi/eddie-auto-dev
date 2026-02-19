package main

import (
	"encoding/json"
	"net/http"
	"testing"

	"github.com/stretchr/testify/assert"
)

// TestCreateIssue tests the CreateIssue method of GoAgent
func TestCreateIssue(t *testing.T) {
	jiraAPI := &JiraAPI{} // Implemente a lógica para criar o Jira API

	goAgent := &GoAgent{jiraAPI: jiraAPI}
	httpServer := &HTTPServer{goAgent: goAgent}

	// Test case 1: Create an issue with valid data
	testIssue := Issue{
		Summary: "Test Issue",
		Description: "This is a test issue.",
	}
	expectedResponse := `{"issue":"created","message":"Issue created successfully"}`
	err := httpServer.goAgent.CreateIssue(testIssue.Summary, testIssue.Description)
	if err != nil {
		t.Errorf("CreateIssue failed with error: %v", err)
	}

	// Test case 2: Create an issue with invalid data
	testInvalidIssue := Issue{
		Summary: "",
		Description: "This is a test issue.",
	}
	expectedError := `{"error":"Invalid request body","message":"Failed to create issue"}`
	err = httpServer.goAgent.CreateIssue(testInvalidIssue.Summary, testInvalidIssue.Description)
	if err == nil {
		t.Errorf("CreateIssue did not return an error with invalid data")
	} else if !assert.Equal(t, expectedError, err.Error()) {
		t.Errorf("CreateIssue returned unexpected error: %v", err)
	}
}

// TestUpdateIssue tests the UpdateIssue method of GoAgent
func TestUpdateIssue(t *testing.T) {
	jiraAPI := &JiraAPI{} // Implemente a lógica para criar o Jira API

	goAgent := &GoAgent{jiraAPI: jiraAPI}
	httpServer := &HTTPServer{goAgent: goAgent}

	// Test case 1: Update an issue with valid data
	testIssueUpdate := IssueUpdate{
		IssueKey: "TEST-1",
		Summary: "Updated Test Issue",
		Description: "This is an updated test issue.",
	}
	expectedResponse := `{"issue":"updated","message":"Issue updated successfully"}`
	err := httpServer.goAgent.UpdateIssue(testIssueUpdate.IssueKey, testIssueUpdate.Summary, testIssueUpdate.Description)
	if err != nil {
		t.Errorf("UpdateIssue failed with error: %v", err)
	}

	// Test case 2: Update an issue with invalid data
	testInvalidIssueUpdate := IssueUpdate{
		IssueKey: "",
		Summary: "Updated Test Issue",
		Description: "This is an updated test issue.",
	}
	expectedError := `{"error":"Invalid request body","message":"Failed to update issue"}`
	err = httpServer.goAgent.UpdateIssue(testInvalidIssueUpdate.IssueKey, testInvalidIssueUpdate.Summary, testInvalidIssueUpdate.Description)
	if err == nil {
		t.Errorf("UpdateIssue did not return an error with invalid data")
	} else if !assert.Equal(t, expectedError, err.Error()) {
		t.Errorf("UpdateIssue returned unexpected error: %v", err)
	}
}

// TestHTTPServer tests the ServeHTTP method of HTTPServer
func TestHTTPServer(t *testing.T) {
	jiraAPI := &JiraAPI{} // Implemente a lógica para criar o Jira API

	goAgent := &GoAgent{jiraAPI: jiraAPI}
	httpServer := &HTTPServer{goAgent: goAgent}

	// Test case 1: Create an issue
	testIssue := Issue{
		Summary: "Test Issue",
		Description: "This is a test issue.",
	}
	expectedResponse := `{"issue":"created","message":"Issue created successfully"}`
	err := httpServer.goAgent.CreateIssue(testIssue.Summary, testIssue.Description)
	if err != nil {
		t.Errorf("CreateIssue failed with error: %v", err)
	}

	// Test case 2: Update an issue
	testIssueUpdate := IssueUpdate{
		IssueKey: "TEST-1",
		Summary: "Updated Test Issue",
		Description: "This is an updated test issue.",
	}
	expectedResponse := `{"issue":"updated","message":"Issue updated successfully"}`
	err = httpServer.goAgent.UpdateIssue(testIssueUpdate.IssueKey, testIssueUpdate.Summary, testIssueUpdate.Description)
	if err != nil {
		t.Errorf("UpdateIssue failed with error: %v", err)
	}

	// Test case 3: Handle invalid request
	expectedError := `{"error":"Invalid request body","message":"Failed to create issue"}`
	err = httpServer.goAgent.CreateIssue("", "")
	if err == nil {
		t.Errorf("CreateIssue did not return an error with invalid data")
	} else if !assert.Equal(t, expectedError, err.Error()) {
		t.Errorf("CreateIssue returned unexpected error: %v", err)
	}
}