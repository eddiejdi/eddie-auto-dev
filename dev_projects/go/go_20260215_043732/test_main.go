package main_test

import (
	"testing"
)

// TestNewJiraClient verifica se NewJiraClient retorna uma instância de JiraClient
func TestNewJiraClient(t *testing.T) {
	jc := NewJiraClient()
	if jc == nil {
		t.Errorf("NewJiraClient should return a non-nil instance")
	}
}

// TestTrackIssue verifica se TrackIssue registra a atividade corretamente
func TestTrackIssue(t *testing.T) {
	jc := NewJiraClient()
	err := jc.TrackIssue("12345", "In Progress")
	if err != nil {
		t.Errorf("TrackIssue should return no error for valid inputs")
	}
}

// TestTrackIssueError verifica se TrackIssue retorna um erro para valores inválidos
func TestTrackIssueError(t *testing.T) {
	jc := NewJiraClient()
	err := jc.TrackIssue("12345", "")
	if err == nil {
		t.Errorf("TrackIssue should return an error for empty status")
	}
}

// TestTrackIssueEdgeCase verifica se TrackIssue funciona corretamente com valores limite
func TestTrackIssueEdgeCase(t *testing.T) {
	jc := NewJiraClient()
	err := jc.TrackIssue("", "In Progress")
	if err != nil {
		t.Errorf("TrackIssue should return an error for empty issue ID")
	}
}

// TestTrackIssueNone verifica se TrackIssue funciona corretamente com None
func TestTrackIssueNone(t *testing.T) {
	jc := NewJiraClient()
	err := jc.TrackIssue(nil, "In Progress")
	if err != nil {
		t.Errorf("TrackIssue should return an error for nil issue ID")
	}
}