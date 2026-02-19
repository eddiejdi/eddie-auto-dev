package main

import (
	"testing"
)

// TestJiraClientCreateIssue tests the CreateIssue method of JiraAPI
func TestJiraClientCreateIssue(t *testing.T) {
	jira := &JiraAPI{}
	err := jira.CreateIssue("New Feature Request", "Implement a new feature in the application")
	if err != nil {
		t.Errorf("Expected no error, got %v", err)
	}
}

// TestGoAgentClientTrackActivity tests the TrackActivity method of GoAgentAPI
func TestGoAgentClientTrackActivity(t *testing.T) {
	goAgent := &GoAgentAPI{}
	err := goAgent.TrackActivity("Feature Implementation")
	if err != nil {
		t.Errorf("Expected no error, got %v", err)
	}
}