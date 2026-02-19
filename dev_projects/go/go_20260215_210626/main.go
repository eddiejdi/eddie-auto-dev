package main

import (
	"fmt"
	"log"

	"github.com/yourusername/go-agent-jira"
)

func main() {
	// Configuração do Go Agent com Jira
	config := &goagentjira.Config{
		JiraURL:    "https://your-jira-instance.atlassian.net",
		Username:  "your-username",
		Password:  "your-password",
	}

	// Cria um novo cliente de Go Agent para Jira
	client, err := goagentjira.NewClient(config)
	if err != nil {
		log.Fatalf("Failed to create Go Agent client: %v", err)
	}

	// Função para criar uma nova tarefa
	createTask := func(title, description string) error {
		task, err := client.CreateIssue(&goagentjira.Issue{
			Title:    title,
			Description: description,
			Type: &goagentjira.Type{
				Name: "Bug",
			},
		})
		if err != nil {
			return fmt.Errorf("Failed to create task: %v", err)
		}
		fmt.Printf("Task created with ID: %s\n", task.ID)
		return nil
	}

	// Função para atualizar uma tarefa
	updateTask := func(taskID string, title, description string) error {
		task, err := client.UpdateIssue(&goagentjira.Issue{
			ID:       taskID,
			Title:    title,
			Description: description,
		})
		if err != nil {
			return fmt.Errorf("Failed to update task: %v", err)
		}
		fmt.Printf("Task updated with ID: %s\n", task.ID)
		return nil
	}

	// Função para deletar uma tarefa
	deleteTask := func(taskID string) error {
		err := client.DeleteIssue(taskID)
		if err != nil {
			return fmt.Errorf("Failed to delete task: %v", err)
		}
		fmt.Printf("Task deleted with ID: %s\n", taskID)
		return nil
	}

	// Exemplos de uso das funções
	err = createTask("Bug in Go Agent integration", "We need a better way to integrate Go Agent with Jira.")
	if err != nil {
		log.Fatalf("Error creating task: %v", err)
	}

	err = updateTask("Bug in Go Agent integration", "The current implementation of the integration is not working as expected.")
	if err != nil {
		log.Fatalf("Error updating task: %v", err)
	}

	err = deleteTask("12345")
	if err != nil {
		log.Fatalf("Error deleting task: %v", err)
	}
}