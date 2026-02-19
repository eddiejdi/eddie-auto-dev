import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraException;
import com.atlassian.jira.project.Project;

public class JavaAgentJiraIntegration {

    public static void main(String[] args) {
        // Configuração do Jira (substitua pelos valores corretos)
        String jiraUrl = "http://your-jira-url";
        String username = "your-username";
        String password = "your-password";

        try {
            // Inicializa o Jira
            Jira jira = new Jira(jiraUrl, username, password);

            // Cria um novo projeto (substitua pelos valores corretos)
            Project project = jira.createProject("My Project", "My Project Description");

            System.out.println("Project created successfully: " + project.getName());

        } catch (JiraException e) {
            e.printStackTrace();
        }
    }
}