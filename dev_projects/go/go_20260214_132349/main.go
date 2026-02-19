package main

import (
	"fmt"
	"net/http"
)

// JiraClient é a interface para interagir com o Jira API.
type JiraClient interface {
	CreateIssue(title, description string) error
}

// GoAgentClient é a interface para interagir com o Go Agent API.
type GoAgentClient interface {
	SendEvent(eventType string, eventData map[string]interface{}) error
}

// JiraAPI implementa a interface JiraClient para interagir com o Jira API.
type JiraAPI struct{}

func (j *JiraAPI) CreateIssue(title, description string) error {
	// Simulação de chamada à API do Jira
	fmt.Printf("Creating issue: %s - %s\n", title, description)
	return nil
}

// GoAgentAPI implementa a interface GoAgentClient para interagir com o Go Agent API.
type GoAgentAPI struct{}

func (g *GoAgentAPI) SendEvent(eventType string, eventData map[string]interface{}) error {
	// Simulação de chamada à API do Go Agent
	fmt.Printf("Sending event: %s - %+v\n", eventType, eventData)
	return nil
}

// TrackActivity realiza o tracking da atividade no Jira e Go Agent.
func TrackActivity(jiraClient JiraClient, goAgentClient GoAgentClient) {
	title := "New Feature Request"
	description := "Request to implement a new feature in the application."

	// Criando issue no Jira
	err := jiraClient.CreateIssue(title, description)
	if err != nil {
		fmt.Printf("Failed to create issue: %v\n", err)
		return
	}

	// Enviando evento no Go Agent
	eventData := map[string]interface{}{
		"eventType": "featureRequest",
		"title":    title,
		"description": description,
	}
	err = goAgentClient.SendEvent("featureRequest", eventData)
	if err != nil {
		fmt.Printf("Failed to send event: %v\n", err)
		return
	}

	fmt.Println("Activity tracked successfully.")
}

func main() {
	jira := &JiraAPI{}
	goAgent := &GoAgentAPI{}

	TrackActivity(jira, goAgent)
}