package main

import (
	"fmt"
	"log"
)

// JiraClient representa a interface para interagir com o Jira API
type JiraClient interface {
	CreateIssue(title, description string) error
	UpdateIssue(issueID int, title, description string) error
}

// GoAgentClient representa a interface para interagir com o Go Agent API
type GoAgentClient interface {
	SubmitBuild(buildID int, status string) error
}

// Jira implements the JiraClient interface
type Jira struct{}

func (j *Jira) CreateIssue(title, description string) error {
	fmt.Printf("Creating issue: %s\n", title)
	return nil
}

func (j *Jira) UpdateIssue(issueID int, title, description string) error {
	fmt.Printf("Updating issue %d: %s\n", issueID, title)
	return nil
}

// GoAgent implements the GoAgentClient interface
type GoAgent struct{}

func (g *GoAgent) SubmitBuild(buildID int, status string) error {
	fmt.Printf("Submitting build %d with status: %s\n", buildID, status)
	return nil
}

// Main function to demonstrate the integration of Go Agent with Jira
func main() {
	jira := &Jira{}
	goAgent := &GoAgent{}

	err := jira.CreateIssue("New Feature Request", "Implement a new feature")
	if err != nil {
		log.Fatalf("Error creating issue: %v\n", err)
	}

	err = goAgent.SubmitBuild(123, "SUCCESS")
	if err != nil {
		log.Fatalf("Error submitting build: %v\n", err)
	}
}