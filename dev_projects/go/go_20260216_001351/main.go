package main

import (
	"fmt"
	"net/http"
)

// JiraClient é a interface para interagir com o Jira API
type JiraClient interface {
	CreateIssue(title, description string) error
}

// GoAgentClient é a interface para interagir com o Go Agent API
type GoAgentClient interface {
	TrackActivity(activityName string) error
}

// JiraAPI implementa a JiraClient interface
type JiraAPI struct{}

func (j *JiraAPI) CreateIssue(title, description string) error {
	// Simulação de chamada à API do Jira
	fmt.Printf("Creating issue '%s' with description: %s\n", title, description)
	return nil
}

// GoAgentAPI implementa a GoAgentClient interface
type GoAgentAPI struct{}

func (g *GoAgentAPI) TrackActivity(activityName string) error {
	// Simulação de chamada à API do Go Agent
	fmt.Printf("Tracking activity '%s'\n", activityName)
	return nil
}

// Main é o ponto principal da aplicação
func main() {
	jiraClient := &JiraAPI{}
	goAgentClient := &GoAgentAPI{}

	err := jiraClient.CreateIssue("New Feature Request", "Implement a new feature in the application")
	if err != nil {
		fmt.Println(err)
		return
	}

	err = goAgentClient.TrackActivity("Feature Implementation")
	if err != nil {
		fmt.Println(err)
		return
	}
}