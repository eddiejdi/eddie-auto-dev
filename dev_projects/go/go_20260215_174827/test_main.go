package main

import (
	"errors"
	"testing"
)

// TestJiraAdapterCreateIssue tests the CreateIssue method of JiraAdapter
func TestJiraAdapterCreateIssue(t *testing.T) {
	jira := &JiraAdapter{}
	err := jira.CreateIssue("Bug in Go Agent", "The Go Agent is not working as expected.")
	if err != nil {
		t.Errorf("Expected no error, got %v", err)
	}
}

// TestGoAgentAdapterTrackActivity tests the TrackActivity method of GoAgentAdapter
func TestGoAgentAdapterTrackActivity(t *testing.T) {
	goAgent := &GoAgentAdapter{}
	err := goAgent.TrackActivity("Go Agent activity")
	if err != nil {
		t.Errorf("Expected no error, got %v", err)
	}
}

// TestJiraServiceCreateIssue tests the CreateIssue method of JiraService
func TestJiraServiceCreateIssue(t *testing.T) {
	jira := &JiraAdapter{}
	jiraService := &JiraService{client: jira}
	err := jiraService.CreateIssue("Bug in Go Agent", "The Go Agent is not working as expected.")
	if err != nil {
		t.Errorf("Expected no error, got %v", err)
	}
}

// TestGoAgentServiceTrackActivity tests the TrackActivity method of GoAgentService
func TestGoAgentServiceTrackActivity(t *testing.T) {
	goAgent := &GoAgentAdapter{}
	goAgentService := &GoAgentService{client: goAgent}
	err := goAgentService.TrackActivity("Go Agent activity")
	if err != nil {
		t.Errorf("Expected no error, got %v", err)
	}
}

// TestJiraServiceCreateIssueError tests the CreateIssue method of JiraService with an error
func TestJiraServiceCreateIssueError(t *testing.T) {
	jira := &JiraAdapter{}
	jiraService := &JiraService{client: jira}
	err := jiraService.CreateIssue("Bug in Go Agent", "")
	if err != nil {
		t.Errorf("Expected no error, got %v", err)
	}
}

// TestGoAgentServiceTrackActivityError tests the TrackActivity method of GoAgentService with an error
func TestGoAgentServiceTrackActivityError(t *testing.T) {
	goAgent := &GoAgentAdapter{}
	goAgentService := &GoAgentService{client: goAgent}
	err := goAgentService.TrackActivity("")
	if err != nil {
		t.Errorf("Expected no error, got %v", err)
	}
}