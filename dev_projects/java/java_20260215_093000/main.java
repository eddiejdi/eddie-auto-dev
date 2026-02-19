import com.atlassian.jira.ComponentManager;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomField;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.TextField;
import com.atlassian.jira.user.User;

public class JavaAgent {

    public static void main(String[] args) {
        // Configuração do JIRA
        ComponentManager componentManager = ComponentManager.getInstance();
        FieldManager fieldManager = componentManager.getFieldManager();

        // Criação de um novo issue
        Issue issue = fieldManager.createIssue("My New Issue", "This is a test issue");

        // Adição de campos personalizados ao issue
        CustomField customField1 = fieldManager.getCustomFieldObjectByName("Custom Field 1");
        TextField textField1 = (TextField) customField1.getField();
        textField1.setValue(issue, "Value for Custom Field 1");

        CustomField customField2 = fieldManager.getCustomFieldObjectByName("Custom Field 2");
        TextField textField2 = (TextField) customField2.getField();
        textField2.setValue(issue, "Value for Custom Field 2");

        // Adição de um usuário ao issue
        User user = componentManager.getUserManager().getUserByKey("username");
        issue.addWatcher(user);

        // Salva o issue no JIRA
        try {
            issue.update();
        } catch (Exception e) {
            System.err.println("Error saving issue: " + e.getMessage());
        }
    }
}