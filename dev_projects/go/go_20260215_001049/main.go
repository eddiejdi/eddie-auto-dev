package main

import (
	"fmt"
	"net/http"
)

// JiraClient é a interface para interagir com o Jira API
type JiraClient interface {
	CreateIssue(title string, description string) error
}

// GoAgentClient é a interface para interagir com o Go Agent API
type GoAgentClient interface {
	SendEvent(eventType string, eventData map[string]string) error
}

// JiraAPI implementa a interface JiraClient
type JiraAPI struct{}

func (j *JiraAPI) CreateIssue(title string, description string) error {
	// Simulação de chamada à API do Jira
	fmt.Printf("Creating issue: %s\n", title)
	return nil
}

// GoAgentAPI implementa a interface GoAgentClient
type GoAgentAPI struct{}

func (g *GoAgentAPI) SendEvent(eventType string, eventData map[string]string) error {
	// Simulação de chamada à API do Go Agent
	fmt.Printf("Sending event: %s\n", eventType)
	return nil
}

// JiraIntegration é a classe que integra o Go Agent com o Jira
type JiraIntegration struct {
	jiraClient JiraClient
	goAgentClient GoAgentClient
}

func (j *JiraIntegration) TrackActivity(eventType string, eventData map[string]string) error {
	err := j.jiraClient.CreateIssue("Activity Tracking", fmt.Sprintf("Event: %s\nData: %+v", eventType, eventData))
	if err != nil {
		return err
	}
	err = j.goAgentClient.SendEvent(eventType, eventData)
	if err != nil {
		return err
	}
	fmt.Println("Activity tracked successfully")
	return nil
}

func main() {
	jiraAPI := &JiraAPI{}
	goAgentAPI := &GoAgentAPI{}

	integration := JiraIntegration{jiraAPI, goAgentAPI}

	err := integration.TrackActivity("User Activity", map[string]string{"user": "john_doe", "action": "login"})
	if err != nil {
		fmt.Println("Error tracking activity:", err)
		return
	}
}