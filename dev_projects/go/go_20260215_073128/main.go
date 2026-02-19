package main

import (
	"fmt"
	"log"
)

// JiraClient representa uma interface para interagir com a API do Jira.
type JiraClient interface {
	CreateIssue(title, description string) error
}

// GoAgent represents the Go Agent that integrates with Jira.
type GoAgent struct {
	client JiraClient
}

// NewGoAgent creates a new instance of GoAgent.
func NewGoAgent(client JiraClient) *GoAgent {
	return &GoAgent{client: client}
}

// TrackActivity tracks an activity in Jira.
func (g *GoAgent) TrackActivity(title, description string) error {
	err := g.client.CreateIssue(title, description)
	if err != nil {
		log.Printf("Error tracking activity: %v", err)
		return err
	}
	fmt.Println("Activity tracked successfully")
	return nil
}

// main is the entry point of the program.
func main() {
	jiraClient := NewJiraClient(&MockJiraClient{})
	goAgent := GoAgent{jiraClient}

	err := goAgent.TrackActivity("New Feature Request", "Implement a new feature in the application.")
	if err != nil {
		return
	}
}