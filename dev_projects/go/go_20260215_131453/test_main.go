package main

import (
	"testing"
)

// TestJiraClientCreateIssue tests the CreateIssue method of the Jira client.
func TestJiraClientCreateIssue(t *testing.T) {
	jira := &Jira{}
	err := jira.CreateIssue("Test Issue", "This is a test issue.")
	if err != nil {
		t.Errorf("Expected no error, got: %v", err)
	}
}

// TestGoAgentClientSendMetric tests the SendMetric method of the GoAgent client.
func TestGoAgentClientSendMetric(t *testing.T) {
	goAgent := &GoAgent{}
	err := goAgent.SendMetric("go-agent.test", 10.5)
	if err != nil {
		t.Errorf("Expected no error, got: %v", err)
	}
}

// TestJiraClientCreateIssueError tests the CreateIssue method with an error.
func TestJiraClientCreateIssueError(t *testing.T) {
	jira := &Jira{}
	err := jira.CreateIssue("", "")
	if err != nil {
		t.Errorf("Expected no error, got: %v", err)
	}
}

// TestGoAgentClientSendMetricError tests the SendMetric method with an error.
func TestGoAgentClientSendMetricError(t *testing.T) {
	goAgent := &GoAgent{}
	err := goAgent.SendMetric("", 0.0)
	if err != nil {
		t.Errorf("Expected no error, got: %v", err)
	}
}

// TestJiraClientCreateIssueEdgeCase tests the CreateIssue method with edge cases.
func TestJiraClientCreateIssueEdgeCase(t *testing.T) {
	jira := &Jira{}
	err := jira.CreateIssue("Test Issue", "This is a test issue.")
	if err != nil {
		t.Errorf("Expected no error, got: %v", err)
	}
}

// TestGoAgentClientSendMetricEdgeCase tests the SendMetric method with edge cases.
func TestGoAgentClientSendMetricEdgeCase(t *testing.T) {
	goAgent := &GoAgent{}
	err := goAgent.SendMetric("", 0.0)
	if err != nil {
		t.Errorf("Expected no error, got: %v", err)
	}
}