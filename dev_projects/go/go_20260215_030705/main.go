package main

import (
	"fmt"
	"net/http"
)

// JiraClient é uma interface para a comunicação com o Jira API
type JiraClient interface {
	CreateIssue(title, description string) error
}

// GoAgentClient é uma interface para a comunicação com o Go Agent API
type GoAgentClient interface {
	TickleJob(jobID string) error
}

// JiraAPI é um implementação da interface JiraClient
type JiraAPI struct{}

func (j *JiraAPI) CreateIssue(title, description string) error {
	// Simulação de chamada à API do Jira para criar uma nova tarefa
	fmt.Printf("Creating issue '%s' with description: %s\n", title, description)
	return nil
}

// GoAgentAPI é um implementação da interface GoAgentClient
type GoAgentAPI struct{}

func (g *GoAgentAPI) TickleJob(jobID string) error {
	// Simulação de chamada à API do Go Agent para tickler uma tarefa
	fmt.Printf("Tickling job '%s'\n", jobID)
	return nil
}

// JiraService é um serviço que utiliza o JiraClient para criar e ticklar tarefas
type JiraService struct {
	jiraClient JiraClient
	goAgentClient GoAgentClient
}

func (js *JiraService) CreateAndTickleIssue(title, description string) error {
	err := js.jiraClient.CreateIssue(title, description)
	if err != nil {
		return fmt.Errorf("Error creating issue: %w", err)
	}
	err = js.goAgentClient.TickleJob(js.jiraClient.CreateIssue(title, description).ID)
	if err != nil {
		return fmt.Errorf("Error tickling job: %w", err)
	}
	return nil
}

func main() {
	jira := &JiraAPI{}
	goAgent := &GoAgentAPI{}

	service := &JiraService{jira, goAgent}

	err := service.CreateAndTickleIssue("Test Issue", "This is a test issue.")
	if err != nil {
		fmt.Println(err)
		return
	}
	fmt.Println("Issue created and tickled successfully!")
}