package main

import (
	"fmt"
	"net/http"
)

// JiraClient é uma interface para a comunicação com o Jira API
type JiraClient interface {
	CreateIssue(title string, description string) error
}

// GoAgentClient é uma interface para a comunicação com o Go Agent API
type GoAgentClient interface {
	SendReport(report string) error
}

// JiraAPI é um implementação da interface JiraClient
type JiraAPI struct{}

func (j *JiraAPI) CreateIssue(title string, description string) error {
	// Simulação de requisição para criar um issue no Jira
	fmt.Printf("Creating issue: %s - %s\n", title, description)
	return nil
}

// GoAgentAPI é um implementação da interface GoAgentClient
type GoAgentAPI struct{}

func (g *GoAgentAPI) SendReport(report string) error {
	// Simulação de requisição para enviar um relatório no Go Agent
	fmt.Printf("Sending report: %s\n", report)
	return nil
}

// JiraIntegration é uma classe que integra o Go Agent com o Jira
type JiraIntegration struct {
	jiraClient JiraClient
	goAgentClient GoAgentClient
}

func (j *JiraIntegration) TrackActivity(title, description string) error {
	err := j.jiraClient.CreateIssue(title, description)
	if err != nil {
		return fmt.Errorf("Failed to create issue in Jira: %w", err)
	}
	err = j.goAgentClient.SendReport(description)
	if err != nil {
		return fmt.Errorf("Failed to send report to Go Agent: %w", err)
	}
	fmt.Println("Activity tracked successfully")
	return nil
}

func main() {
	jiraAPI := &JiraAPI{}
	goAgentAPI := &GoAgentAPI{}

	integration := JiraIntegration{jiraAPI, goAgentAPI}

	err := integration.TrackActivity("New Feature Request", "Implement a new feature in the application")
	if err != nil {
		fmt.Println(err)
		return
	}
}