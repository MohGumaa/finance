// Jquery ti query password form DB and respose
// JS code to check matching of new and confirm password
$(document).ready(function(){
    $('#confirm').keyup(function(){
        const newpwd = $('#newpwd').val();
        const confirm = $('#confirm').val();
        if (confirm != newpwd){
            $('#warningAlert').text("** Passwords are not matching").show();
    		return false;
        }else {
            $('#warningAlert').text("").hide();
    		return true;
        }

    });
});

