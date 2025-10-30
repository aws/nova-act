() => {
  const ATTRIBUTES_TO_KEEP = new Set([
    "alt",
    "role",
    "placeholder",
    "href",
    "nova-act-id",
    "title",
    "value",
    "scrollable",
    "scrolled-from-top",
    "scrolled-from-left",
    "data-cy",
    "data-test",
    "data-testid",
    "data-test-id",
    "currently-obscured",
  ]);

  function getHorizontalScrollPercentage(element) {
    const scrollAxisSize = element.scrollWidth - element.clientWidth;
    return scrollAxisSize === 0
      ? -1
      : (element.scrollLeft * 100) / scrollAxisSize;
  }

  function getVerticalScrollPercentage(element) {
    const scrollAxisSize = element.scrollHeight - element.clientHeight;
    return scrollAxisSize === 0
      ? -1
      : (element.scrollTop * 100) / scrollAxisSize;
  }

  function getScrollPercentage(element) {
    return {
      left: getHorizontalScrollPercentage(element),
      top: getVerticalScrollPercentage(element),
    };
  }

  function isScrollableElement(element, direction) {
    if (element === document.body) {
      return false;
    }
    const isVertical = ["up", "down"].includes(direction);
    function style(_node, property) {
      return getComputedStyle(_node).getPropertyValue(property);
    }
    function overflow_classes(_node) {
      return (
        style(_node, "overflow") +
        style(_node, isVertical ? "overflow-y" : "overflow-x")
      );
    }
    const classes = overflow_classes(element);
    return (
      (isVertical
        ? element.scrollHeight > element.clientHeight
        : element.scrollWidth > element.clientWidth) &&
      (classes.includes("auto") || classes.includes("scroll"))
    );
  }

  function getGlobalBoundingBox(element) {
    const rect = element.getBoundingClientRect();
    const documentFrameElement =
      element.ownerDocument.defaultView?.frameElement;
    // We need to add the top left of the iframe to the top left of the clicked element,
    // because the clicked element's bounding rectangle coordinates are relative to the iframe.
    if (documentFrameElement) {
      const iframeRect = documentFrameElement.getBoundingClientRect();
      rect.x += iframeRect.left;
      rect.y += iframeRect.top;
    }
    return { height: rect.height, width: rect.width, x: rect.x, y: rect.y };
  }

  function removeAttributesFromHtml(
    document_,
    idToBboxMap,
    additionalAttributesToKeep,
    attributesToRemove
  ) {
    const toKeep = new Set([
      ...ATTRIBUTES_TO_KEEP,
      ...(additionalAttributesToKeep ?? []),
    ]);
    const toRemove = new Set(attributesToRemove ?? []);
    function removeAttributesHelper(node) {
      for (let index = node.attributes.length - 1; index >= 0; index--) {
        const attribute = node.attributes[index];
        if (
          toRemove.has(attribute.name) ||
          (!attribute.name.startsWith("aria") &&
            !(toKeep.has(attribute.name) && attribute.value))
        ) {
          node.removeAttribute(attribute.name);
        }
      }
      if (
        node.attributes.length === 0 &&
        !["IMG", "SVG", "BODY"].includes(node.tagName) &&
        node.children.length === 0 &&
        node instanceof HTMLElement &&
        node.innerText?.trim()?.length === 0
      ) {
        removeNode(node, idToBboxMap);
      } else {
        const children = [...node.children];
        for (const child of children) {
          if (child !== null) removeAttributesHelper(child);
        }
      }
    }
    removeAttributesHelper(document_.body);
  }

  function hasNonWhitespaceTextNodes(node) {
    return [...node.childNodes].some(
      (child) =>
        child.nodeType === Node.TEXT_NODE &&
        (child.textContent || "").trim() !== ""
    );
  }

  function replaceSingleChildParents(document_, idToBboxMap) {
    function checkAndReplace(node) {
      // Enhanced base case: Check not only for single element child but also for non-whitespace text nodes
      if (
        (node.attributes.length === 0 ||
          (node.attributes.length === 1 &&
            node.attributes[0] &&
            node.attributes[0].name === "nova-act-id")) &&
        node.children.length === 1 &&
        node.tagName.toLowerCase() !== "body" &&
        !hasNonWhitespaceTextNodes(node)
      ) {
        const child = node.children[0];
        node.parentNode.replaceChild(child, node);
        if (idToBboxMap && node.hasAttribute("nova-act-id")) {
          idToBboxMap.delete(node.getAttribute("nova-act-id"));
        }
        checkAndReplace(child);
      } else {
        const children = [...node.children];
        for (const child of children) {
          checkAndReplace(child);
        }
      }
    }

    checkAndReplace(document_.body);
  }

  function removeNode(node, idToBboxMap) {
    if (!(node instanceof Element)) {
      node.remove();
      return;
    }
    if (node.children.length > 0) {
      const children = [...node.children];
      for (const child of children) {
        removeNode(child, idToBboxMap);
      }
    }

    if (idToBboxMap && node.hasAttribute("nova-act-id")) {
      idToBboxMap.delete(node.getAttribute("nova-act-id"));
    }

    node.remove();
  }

  function removeAllAttributelessDivs(document_, idToBboxMap) {
    function checkAndRemove(node) {
      const children = [...node.children];
      for (const child of children) {
        checkAndRemove(child);
      }
      if (
        (node.attributes.length === 0 ||
          (node.attributes.length === 1 &&
            node.attributes[0] &&
            node.attributes[0].name === "nova-act-id")) &&
        !["IMG", "SVG", "BODY", "INPUT", "FIELDSET"].includes(node.tagName) &&
        node.children.length === 0 &&
        node instanceof HTMLElement &&
        node.innerText?.trim()?.length === 0
      ) {
        removeNode(node, idToBboxMap);
      }
    }
    checkAndRemove(document_.body);
  }

  function removeScriptTags(document_, idToBboxMap) {
    const scriptTags = document_.querySelectorAll("script");
    for (const script of scriptTags) {
      removeNode(script, idToBboxMap);
    }
    const noScriptTags = document_.querySelectorAll("noscript");
    for (const script of noScriptTags) {
      removeNode(script, idToBboxMap);
    }
  }

  function removeStyleTags(document_, idToBboxMap) {
    const styleTags = document_.querySelectorAll("style");
    for (const style of styleTags) {
      removeNode(style, idToBboxMap);
      if (idToBboxMap) {
        idToBboxMap.delete(style.getAttribute("nova-act-id"));
      }
    }
  }

  function removeChildrenFromAllSVGElements(document_, idToBboxMap) {
    const svgElements = document_.querySelectorAll("svg, g, img");

    for (const svgElement of svgElements) {
      while (svgElement.firstChild) {
        removeNode(svgElement.firstChild, idToBboxMap);
      }

      const attributes = svgElement.attributes;
      for (let index = attributes.length - 1; index >= 0; index--) {
        if (
          !(
            ATTRIBUTES_TO_KEEP.has(attributes[index].name) ||
            attributes[index].name.startsWith("aria")
          )
        ) {
          svgElement.removeAttribute(attributes[index].name);
        }
      }
    }
  }

  function removeUnnecessarySpans(document_, idToBboxMap) {
    const spans = document_.querySelectorAll("span, sub");

    // Convert the HTMLCollection to an array to avoid live collection issues
    const spansArray = [...spans];

    for (const span of spansArray) {
      // Check if the span only contains text
      if (
        span.childNodes.length === 1 &&
        span.childNodes[0]?.nodeType === Node.TEXT_NODE &&
        !(span.role && ["link", "button"].includes(span.role))
      ) {
        const textContent = span.textContent || "";
        const textWithoutNewlines = textContent
          .split("\n")
          .join("")
          .split("\r")
          .join("");
        span.replaceWith(textWithoutNewlines);
        if (idToBboxMap && span.hasAttribute("nova-act-id")) {
          idToBboxMap.delete(span.getAttribute("nova-act-id"));
        }
      }
    }
  }

  function removeComments(document_) {
    function removeCommentsHelper(element) {
      const childNodes = [...element.childNodes];
      for (const child of childNodes) {
        if (child.nodeType == Node.COMMENT_NODE) {
          child.remove();
        } else if (child.nodeType == Node.ELEMENT_NODE) {
          removeCommentsHelper(child);
        }
      }
    }
    removeCommentsHelper(document_.body);
  }

  function isZeroAreaBbox(bbox) {
    return bbox.width === 0 || bbox.height === 0;
  }

  function isIntrinsicallyInvisible(element) {
    return (
      (element.tagName === "OPTION" || element.tagName === "OPTGROUP") &&
      isZeroAreaBbox(getGlobalBoundingBox(element))
    );
  }

  function tagOccludedLeaves(element, idToBboxMap) {
    const nova_act_id = element.getAttribute("nova-act-id") ?? null;
    const bbox = nova_act_id !== null && idToBboxMap.get(nova_act_id);
    if (bbox) {
      const pointsToCheck = [
        { x: bbox.x + bbox.width / 2, y: bbox.y + bbox.height / 2 }, // center
      ];

      // If none of the points contain the element,
      // tag it as not visible and not actuatable,
      // and remove the nova-act-id so that it doesn't get selected
      if (
        pointsToCheck.every(({ x, y }) => {
          // Go through all elements at the point
          for (const element of document.elementsFromPoint(x, y)) {
            // If any elments in the live-DOM match the nova-act-id, then the element is visible
            if (element.getAttribute("nova-act-id") === nova_act_id) {
              return false;
            }
          }
          // If no elements in the live-DOM match the nova-act-id, then the element is invisible
          return true;
        })
      ) {
        element.setAttribute("currently-obscured", "true");
        element.removeAttribute("nova-act-id");
      }
    }
    for (const child of element.children) {
      tagOccludedLeaves(child, idToBboxMap);
    }
  }

  function removeInvisibleLeaves(
    document_,
    idToBboxMap,
    invisibleIdSet,
    removeOutsideViewport
  ) {
    function isOnscreenButZeroArea(element) {
      if (!element.getAttribute("nova-act-id")) return false;
      const bbox = idToBboxMap.get(element.getAttribute("nova-act-id"));
      return bbox
        ? isZeroAreaBbox(bbox) &&
            !(
              bbox.x < 0 ||
              bbox.y < 0 ||
              bbox.x + bbox.width > window.innerWidth ||
              bbox.y + bbox.height > window.innerHeight
            )
        : false;
    }

    function isOffscreen(element) {
      if (!element.getAttribute("nova-act-id")) return true;
      if (element.tagName === "BODY") return false;
      const bbox = idToBboxMap.get(element.getAttribute("nova-act-id"));
      if (!bbox) return true;
      return (
        removeOutsideViewport &&
        (bbox.x < 0 ||
          bbox.y < 0 ||
          bbox.x + bbox.width > window.innerWidth ||
          bbox.y + bbox.height > window.innerHeight)
      );
    }

    function removeInvisibleLeavesHelper(element, parent = null) {
      if (isIntrinsicallyInvisible(element)) return true;

      let numberInstrinsicallyInvisibleChildren = 0;
      // Check and handle children first to ensure bottom-up removal.
      const childNodes = [...element.childNodes];
      for (const childNode of childNodes) {
        if (childNode.nodeType === Node.ELEMENT_NODE) {
          const intrinsicallyInvisible = removeInvisibleLeavesHelper(
            childNode,
            element
          );
          if (intrinsicallyInvisible) numberInstrinsicallyInvisibleChildren++;
        }
      }

      // Check if the element is offscreen (and not just zero area onscreen) to remove it.
      if (
        isOffscreen(element) &&
        numberInstrinsicallyInvisibleChildren === element.childElementCount
      ) {
        removeNode(element, idToBboxMap);
        return false;
      }

      // Check if nova-act-invisible attribute is set to true
      const novaActId = element.getAttribute("nova-act-id");
      if (novaActId && invisibleIdSet.has(novaActId)) {
        removeNode(element, idToBboxMap);
        return false;
      }

      // Handle squashing of onscreen but zero area elements separately.
      if (parent && isOnscreenButZeroArea(element)) {
        while (element.firstChild) {
          parent.insertBefore(element.firstChild, element);
        }
        removeNode(element, idToBboxMap);
      }
      return false;
    }

    removeInvisibleLeavesHelper(document_.body);
  }

  function removeEmptyElements(document_, idToBboxMap) {
    // Removes elements that 1) have no children, 2) have no text content, and 3) have no attributes (or only nova-act-id)
    function removeEmptyElementsHelper(element) {
      const children = [...element.children];
      for (const child of children) {
        removeEmptyElementsHelper(child);
      }
      if (
        element.children.length === 0 &&
        element.attributes.length <= 1 && // Assumes that the only attribute is nova-act-id
        element instanceof HTMLElement &&
        element.innerText?.trim()?.length === 0 &&
        !["INPUT"].includes(element.tagName)
      ) {
        removeNode(element, idToBboxMap);
      }
    }
    removeEmptyElementsHelper(document_.body);
  }

  function isMarkedInvisible(element) {
    // Check if CSS has marked the element as invisible
    const style = window.getComputedStyle(element);
    return (
      style.display === "none" ||
      style.visibility === "hidden" ||
      style.opacity === "0"
    );
  }

  // Takes the document and attaches nova-act-ids to each of the nodes.
  // Also fills the elementMap with the mapping of nova-act-id to css path, so that
  // we can query select the live elements later.
  // It also collects elements that are invisible.
  function fillElementMap(liveElement, idToBboxMap, invisibleIdSet) {
    let id = 1;
    // First figure out the highest ID assigned so far.
    const idTrackingHelper = (node) => {
      const currentId = node.getAttribute("nova-act-id");
      if (currentId) {
        id = Math.max(id, Number.parseInt(currentId, 10) + 1);
      }
      for (const child of node.children) {
        idTrackingHelper(child);
      }
    };
    idTrackingHelper(liveElement);

    const fillHelper = (node) => {
      const currentId = node.getAttribute("nova-act-id");
      const bbox = getGlobalBoundingBox(node);
      if (currentId) {
        idToBboxMap.set(currentId, bbox);
      } else {
        idToBboxMap.set(id.toString(), bbox);
        node.setAttribute("nova-act-id", id.toString());
        id += 1;
      }

      if (isMarkedInvisible(node)) {
        invisibleIdSet.add(node.getAttribute("nova-act-id"));
      }
      for (const child of node.children) {
        fillHelper(child);
      }
    };
    fillHelper(liveElement);
  }

  // Takes the document and figures out which elements are scrollable.
  // Returns a map from nova-act id to the scrollable value.
  // This assumes that nova-act IDs have been assigned already.
  function fillScrollableAttribute(element) {
    const assignScrollPercentages = (node, percentages) => {
      const attributeValuePairs = [
        ["scrolled-from-top", percentages.top],
        ["scrolled-from-left", percentages.left],
      ];
      for (const [attributeName, value] of attributeValuePairs) {
        if (value >= 0) {
          node.setAttribute(attributeName, `${Math.round(value)}%`);
        }
      }
    };
    const fillScrollableMapHelper = (node) => {
      if (node.tagName === "BODY") {
        node.setAttribute("scrollable", "true");
        assignScrollPercentages(
          node,
          getScrollPercentage(document.documentElement)
        );
      } else if (
        isScrollableElement(node, "up") ||
        isScrollableElement(node, "left")
      ) {
        node.setAttribute("scrollable", "true");
        assignScrollPercentages(node, getScrollPercentage(node));
      }
      for (const child of node.children) {
        fillScrollableMapHelper(child);
      }
    };
    fillScrollableMapHelper(element);
  }

  function fillInputValues(element) {
    if (
      element instanceof HTMLInputElement &&
      element.value &&
      element.getAttribute("value") === null
    ) {
      element.setAttribute("value", element.value);
    }
    for (const child of element.children) {
      fillInputValues(child);
    }
  }

  function bodyToString(body) {
    const indentation = "  ";
    let string_ = "";

    const helper = (node, depth) => {
      if (node.nodeType === Node.ELEMENT_NODE) {
        const element = node;
        const tagName = element.tagName.toLowerCase();
        let tagContent = `<${tagName}`;

        for (const attribute of element.attributes) {
          if (attribute.name === "scrollable") {
            tagContent += attribute.value === "true" ? " scrollable" : "";
          } else {
            tagContent += ` ${attribute.name}='${attribute.value}'`;
          }
        }

        // Check for elements without children or text content
        const isEmptyElement =
          element.childNodes.length === 0 ||
          [...element.childNodes].every(
            (child) =>
              child.nodeType === Node.TEXT_NODE && !child.textContent?.trim()
          );

        if (isEmptyElement) {
          string_ += `${indentation.repeat(depth)}${tagContent}/>\n`;
        } else {
          string_ += `${indentation.repeat(depth)}${tagContent}>\n`;
          for (const child of element.childNodes) {
            helper(child, depth + 1);
          }
          string_ += `${indentation.repeat(depth)}</${tagName}>\n`;
        }
      } else if (node.nodeType === Node.TEXT_NODE) {
        const textContent = node.textContent?.trim();
        if (textContent) {
          string_ += `${indentation.repeat(depth)}${textContent}\n`;
        }
      }
    };

    helper(body, 0);
    return string_;
  }

  function safeGetSimplifiedDOM(...args) {
    try {
      return getSimplifiedDOM(...args);
    } catch (e) {
      console.error("Error while getting Simplified DOM", e);
      return "";
    }
  }

  function getSimplifiedDOM(element, viewportOnly, idToBboxMap, options) {
    const invisibleIdSet = new Set();
    if (idToBboxMap) {
      fillElementMap(element, idToBboxMap, invisibleIdSet);
    }

    const {
      additionalAttributesToKeep,
      attributesToRemove,
      includeInvisible,
      includeScripts,
    } = options || {};

    fillScrollableAttribute(element);
    fillInputValues(element);

    // Make copy of document, including non-static elements
    const document_ = document.implementation.createHTMLDocument("");
    // This step clears all existing child nodes from the new document's html element
    while (document_.documentElement.firstChild) {
      document_.documentElement.firstChild.remove();
    }
    if (element.tagName.toLowerCase() === "body") {
      // If the element is <body>, append it directly
      document_.documentElement.append(element.cloneNode(true));
    } else {
      // Otherwise, create a new <body> and append the cloned element to it. This maintains the function calls later on that references document.body
      const body = document_.createElement("body");
      body.append(element.cloneNode(true));
      document_.documentElement.append(body);
    }

    // We can remove the script and style tags from the document before filling the
    // element map since the getPath function uses nth-of-type
    if (includeScripts === false || includeScripts === undefined) {
      removeScriptTags(document_, idToBboxMap);
    }
    removeStyleTags(document_, idToBboxMap);

    if (viewportOnly && !idToBboxMap) {
      throw new Error("Need id to bbox path map to get viewport only");
    }
    if (idToBboxMap) {
      if (!includeInvisible) {
        removeInvisibleLeaves(
          document_,
          idToBboxMap,
          invisibleIdSet,
          viewportOnly ?? false
        );
      }
      tagOccludedLeaves(document_.body, idToBboxMap);
    }
    removeAttributesFromHtml(
      document_,
      idToBboxMap,
      additionalAttributesToKeep,
      attributesToRemove
    );
    removeAllAttributelessDivs(document_, idToBboxMap);
    removeUnnecessarySpans(document_, idToBboxMap);
    replaceSingleChildParents(document_, idToBboxMap);
    removeChildrenFromAllSVGElements(document_, idToBboxMap);
    removeComments(document_);
    removeEmptyElements(document_, idToBboxMap);
    return bodyToString(document_.body);
  }

  const idToBboxMap = new Map();
  const returnSimplifiedDOM = safeGetSimplifiedDOM(
    document.body,
    true,
    idToBboxMap
  );
  
  // Convert Map to a plain object for return
  const bboxesObject = {};
  idToBboxMap.forEach((value, key) => {
    bboxesObject[key] = value;
  });
  
  const results = {
    bboxes: bboxesObject,
    modifiedHtml: returnSimplifiedDOM,
  };

  return results;
};
