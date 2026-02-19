package main

import (
	"testing"
)

// TestCreateIssue tests the CreateIssue method of GoAgent
func TestCreateIssue(t *testing.T) {
	jiraClient := &JiraClientImpl{} // Implementação da interface JiraClient

	goAgent := NewGoAgent(jiraClient)
	err := goAgent.CreateIssue("Test Issue", "This is a test issue.")
	if err != nil {
		t.Errorf("Error creating issue: %v", err)
	}
}

// TestGetIssues tests the GetIssues method of GoAgent
func TestGetIssues(t *testing.T) {
	jiraClient := &JiraClientImpl{} // Implementação da interface JiraClient

	goAgent := NewGoAgent(jiraClient)
	issues, err := goAgent.GetIssues()
	if err != nil {
		t.Errorf("Error getting issues: %v", err)
	}
}

// TestMonitorProcessos tests the MonitorProcessos method of GoAgent
func TestMonitorProcessos(t *testing.T) {
	jiraClient := &JiraClientImpl{} // Implementação da interface JiraClient

	goAgent := NewGoAgent(jiraClient)
	err := goAgent.MonitorProcessos()
	if err != nil {
		t.Errorf("Error monitoring processes: %v", err)
	}
}

// TestRegistroEventos tests the RegistroEventos method of GoAgent
func TestRegistroEventos(t *testing.T) {
	jiraClient := &JiraClientImpl{} // Implementação da interface JiraClient

	goAgent := NewGoAgent(jiraClient)
	err := goAgent.RegistroEventos("Test Event")
	if err != nil {
		t.Errorf("Error registering event: %v", err)
	}
}