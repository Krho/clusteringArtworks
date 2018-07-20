function allowDrop(ev) {
    ev.preventDefault();
}

function drag(ev) {
  console.log("Draging")
  ev.dataTransfer.setData("text", ev.target.id);
}

function drop(ev) {
    ev.preventDefault();
    var data = ev.dataTransfer.getData("text");
    img = document.getElementById(data)
    //Clean-up
    elements = document.getElementsByName(img.id)
    for (const element of elements){
    	element.setAttribute("name", "")
    }
    //Target
    ev.target.appendChild(img);
    img.setAttribute("name", ev.target.id)
}

function harvest(){
	result = []
	clusters = document.getElementsByClassName("cluster")
	for (const cluster of clusters){
		tag = cluster.getAttribute("tag")
		elementData = {"text":null, "images":[]}
		elements = document.getElementsByName(tag)
		for (const element of elements){

			if (element.type === "text"){
				elementData["text"]=element.value
			} else {
				elementData["images"].push(element.getAttribute("id"))
			}
		}
		result.push(elementData)
	}
	console.log(result)
	return result
}

// Executed at the end of the load
$(function() {
    $('input#load').bind('click', function() {
      $.getJSON($SCRIPT_ROOT + '/load', {
        category: $('input[name="category"]').val()
      }, function(data) {
        $("#result").text(data.result);
      });
      return false;
    });
});
