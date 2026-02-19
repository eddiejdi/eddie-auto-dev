package main

import (
	"fmt"
	"net/http"
)

// JiraClient é uma interface que representa a comunicação com o Jira API.
type JiraClient interface {
	CreateIssue(title string, description string) error
}

// JiraAPI é um implementação da interface JiraClient para a comunicação com o Jira API.
type JiraAPI struct{}

func (j *JiraAPI) CreateIssue(title string, description string) error {
	// Simulação de chamada à API do Jira
	fmt.Printf("Creating issue: %s - %s\n", title, description)
	return nil
}

// GoAgentClient é uma interface que representa a comunicação com o Go Agent.
type GoAgentClient interface {
	SendEvent(event string) error
}

// GoAgentAPI é um implementação da interface GoAgentClient para a comunicação com o Go Agent API.
type GoAgentAPI struct{}

func (g *GoAgentAPI) SendEvent(event string) error {
	// Simulação de chamada à API do Go Agent
	fmt.Printf("Sending event: %s\n", event)
	return nil
}

// Scrum11 implements the JiraClient and GoAgentClient interfaces.
type Scrum11 struct {
	jiraAPI *JiraAPI
	goAgentAPI *GoAgentAPI
}

func (s *Scrum11) CreateIssue(title string, description string) error {
	err := s.jiraAPI.CreateIssue(title, description)
	if err != nil {
		return fmt.Errorf("Failed to create issue in Jira: %w", err)
	}
	err = s.goAgentAPI.SendEvent(fmt.Sprintf("New issue created: %s - %s", title, description))
	if err != nil {
		return fmt.Errorf("Failed to send event to Go Agent: %w", err)
	}
	return nil
}

func main() {
	jira := &JiraAPI{}
	goAgent := &GoAgentAPI{}

	scrum11 := &Scrum11{jira, goAgent}

	err := scrum11.CreateIssue("Bug in Go Agent", "The Go Agent is not working as expected.")
	if err != nil {
		fmt.Println(err)
		return
	}
	fmt.Println("Issue created and event sent successfully.")
}